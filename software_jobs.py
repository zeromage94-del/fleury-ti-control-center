"""Fila persistente de software. Duas estações por vez, operações seriadas por alvo."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import uuid


class Manager:
    def __init__(self, db, audit, now, execute):
        self.db, self.audit, self.now, self.execute = db, audit, now, execute
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='software')
        self.lock = threading.RLock()
        self.target_locks = {}

    def recover(self):
        with self.db() as c:
            c.execute("UPDATE software_jobs SET state='interrupted',updated_at=? WHERE state IN ('queued','running')",(self.now(),))

    def submit(self, target, operation, keys, ids):
        fingerprint = hashlib.sha256(json.dumps([target.lower(),operation,sorted(keys)]).encode()).hexdigest()
        with self.lock, self.db() as c:
            old = c.execute("SELECT id FROM software_jobs WHERE fingerprint=? AND state IN ('queued','running')",(fingerprint,)).fetchone()
            if old:
                return {'job_id':old['id'],'duplicate':True}
            if c.execute("SELECT COUNT(*) FROM software_jobs WHERE state IN ('queued','running')").fetchone()[0] >= 50:
                raise ValueError('Fila cheia; aguarde tarefas em execução.')
            ident = uuid.uuid4().hex
            c.execute('INSERT INTO software_jobs(id,target,operation,packages,state,created_at,updated_at,fingerprint) VALUES(?,?,?,?,?,?,?,?)',
                      (ident,target,operation,json.dumps(keys),'queued',self.now(),self.now(),fingerprint))
        self.audit('Software em fila: '+operation,target,True,'job='+ident+'; escopo=machine; '+', '.join(ids))
        self.pool.submit(self.run,ident,target,operation,ids)
        return {'job_id':ident,'duplicate':False}

    def run(self, ident, target, operation, ids):
        with self.lock:
            target_lock = self.target_locks.setdefault(target.lower(),threading.Lock())
        with target_lock:
            with self.db() as c:
                c.execute("UPDATE software_jobs SET state='running',updated_at=? WHERE id=?",(self.now(),ident))
            try:
                result = self.execute(target,operation,ids)
                items = result.get('Instalacoes' if operation=='install' else 'Desinstalacoes',[])
                if isinstance(items,dict): items=[items]
                success = len(items)==len(ids) and all(x.get('CodigoSaida') in (0,3010) for x in items)
                state = 'succeeded' if success else 'failed'
                error = '' if success else 'Consulte os códigos de saída por pacote. Nenhum fallback para usuário foi executado.'
            except Exception as exc:
                result, state, error = {}, 'failed', str(exc)[:700]
            with self.db() as c:
                c.execute('UPDATE software_jobs SET state=?,result=?,error=?,updated_at=? WHERE id=?',
                          (state,json.dumps(result,ensure_ascii=False),error,self.now(),ident))
            self.audit('Software finalizado: '+operation,target,state=='succeeded',
                       'job='+ident+'; escopo=machine; '+error)

    def list(self):
        with self.db() as c:
            result = [dict(x) for x in c.execute('SELECT * FROM software_jobs ORDER BY created_at DESC LIMIT 50')]
        for item in result:
            item['packages']=json.loads(item['packages'])
            item['result']=json.loads(item['result'] or '{}')
            item.pop('fingerprint',None)
        return result
