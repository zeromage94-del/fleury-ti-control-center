"""Executa regressões sem equipamentos reais e salva evidência JSON desta execução."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time
import unittest
import uuid


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.current = {}

    def startTest(self, test):
        super().startTest(test)
        self.current[test.id()] = dict(test=test.id(), status='passed', subtests=[], started=time.monotonic())

    def mark(self, test, status, detail=None):
        record = self.current.get(test.id())
        if record:
            record['status'] = status
            if detail:
                record['detail'] = detail

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.mark(test, 'failed', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.mark(test, 'error', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.mark(test, 'skipped', reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.mark(test, 'expected_failure')

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.mark(test, 'unexpected_success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        record = self.current.get(test.id())
        if record:
            entry = dict(case=str(subtest), status='passed' if err is None else 'failed')
            if err:
                entry['detail'] = self._exc_info_to_string(err, subtest)
                record['status'] = 'failed'
            record['subtests'].append(entry)

    def stopTest(self, test):
        record = self.current.pop(test.id(), None)
        if record:
            record['seconds'] = round(time.monotonic() - record.pop('started'), 4)
            record['checks'] = list(getattr(test, 'evidence', []))
            self.records.append(record)
        super().stopTest(test)


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern', default='test_*.py', help='Padrão unittest; padrão executa todas regressões Python.')
    parser.add_argument('--output', type=Path, default=root / '.test-temp' / 'simulation-report.json')
    args = parser.parse_args(argv)
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    counts = {name: sum(item['status'] == name for item in result.records)
              for name in ('passed', 'failed', 'error', 'skipped', 'expected_failure', 'unexpected_success')}
    report = dict(schema_version=1, run_id=str(uuid.uuid4()), started_at=started_at,
                  completed_at=datetime.now(timezone.utc).isoformat(),
                  seconds=round(time.monotonic() - start, 4), pattern=args.pattern,
                  platform=platform.system(), python=platform.python_version(),
                  tests_run=result.testsRun, counts=counts,
                  successful=result.wasSuccessful() and result.testsRun > 0,
                  limitations=[
                      'HTTP loopback, SQLite e arquivos temporários reais; Windows/WinRM e equipamentos simulados.',
                      'Os scripts PowerShell não são executados por este adaptador Linux.',
                      'Simulação não valida desempenho físico, drivers reais, firmware, impressão física ou políticas do domínio.',
                      'Teste do parser PowerShell exige Windows; resultados skipped permanecem distintos de passed.',
                  ], records=result.records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + '.' + report['run_id'] + '.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(args.output)
    print('Relatório da execução atual:', args.output)
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
