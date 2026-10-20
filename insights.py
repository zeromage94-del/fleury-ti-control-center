"""Indicadores transparentes da fila local. Nenhum SLA é presumido."""
from collections import Counter
from datetime import datetime, timezone
import re

CATEGORIES = ('Lentidão', 'Disco 100%', 'Impressora Zebra', 'PINPAD / TEF',
              'Impressão geral', 'Rede', 'Sistema Windows', 'Outros', 'Não classificado')

def suggest_category(title):
    t = str(title or '').casefold()
    if re.search(r'(100\s*%|disco\s*100|hd\s*100|disco\s*cheio|alta\s*utiliza[cç][aã]o\s*d[eo]\s*disco)', t): return 'Disco 100%'
    if re.search(r'(zebra|etiqueta|zdesigner|zpl|zt[0-9]{3}|zd[0-9]{3})', t): return 'Impressora Zebra'
    if re.search(r'(pinpad|pin.pad|tef|pagamento|maquininha|sitetef|paygo)', t): return 'PINPAD / TEF'
    if re.search(r'(lent[oaã]|travand|demorand|desempenho|performance)', t): return 'Lentidão'
    if re.search(r'(impress|spooler|fila\s*de\s*impress)', t): return 'Impressão geral'
    if re.search(r'(internet|rede|dns|conex[aã]o|wi.?fi|ethernet)', t): return 'Rede'
    if re.search(r'(windows|atualiza[cç][aã]o|sistema\s*operacional)', t): return 'Sistema Windows'
    return 'Não classificado'

def parse_date(value):
    if not value: return None
    try:
        d = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError): return None

def metrics(tickets):
    total = len(tickets)
    done = [t for t in tickets if t['status'] == 'Resolvido']
    counts = Counter((t.get('category') if t.get('category') in CATEGORIES else 'Não classificado') for t in tickets)
    ranking = [{'category': category, 'count': count, 'percentage': round(100*count/total, 1)}
               for category, count in counts.most_common() if total]
    durations = []
    sla_eligible = 0; sla_met = 0; open_late = 0
    now = datetime.now(timezone.utc)
    for t in tickets:
        created, resolved, deadline = map(parse_date, (t.get('created_at'),t.get('resolved_at'),t.get('sla_due_at')))
        if t['status'] == 'Resolvido' and created and resolved and resolved >= created:
            durations.append((resolved - created).total_seconds()/3600)
        if deadline:
            if t['status'] == 'Resolvido' and resolved:
                sla_eligible += 1
                sla_met += int(resolved <= deadline)
            elif t['status'] != 'Resolvido' and deadline < now:
                open_late += 1
    return {
        'total': total, 'resolved': len(done), 'pending': total-len(done),
        'resolution_pct': round(len(done)*100/total,1) if total else None,
        'avg_resolution_hours': round(sum(durations)/len(durations),1) if durations else None,
        'avg_resolution_count': len(durations),
        'sla_evaluated': sla_eligible, 'sla_met': sla_met, 'sla_missed': sla_eligible-sla_met,
        'sla_pct': round(100*sla_met/sla_eligible,1) if sla_eligible else None,
        'sla_open_overdue': open_late,
        'ranking': ranking,
        'note': 'Ranking calculado sobre os tickets cadastrados; categorias sugeridas por título podem exigir revisão. SLA só é calculado quando existem datas de criação, conclusão e prazo.'
    }
