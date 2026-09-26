"""Atomic, persistent admission quotas. These are reserves, not an OpenAI invoice."""
import os
from datetime import datetime, timezone
from uuid import uuid4


class BudgetDenied(ValueError):
    pass


class AIBudget:
    # Conservative per-attempt allocation; no refunds on timeouts or failures.
    RESERVES = {'text': 20000, 'web': 100000, 'embedding': 10000}

    def __init__(self, db):
        self.db = db

    def limits(self):
        try:
            daily = float(os.getenv('OPENAI_DAILY_RESERVE_USD', '1'))
            total = float(os.getenv('OPENAI_TOTAL_RESERVE_USD', '10'))
            if not 0 <= daily <= 10 or not 0 <= total <= 40:
                raise ValueError()
            return int(daily * 1000000), int(total * 1000000)
        except ValueError:
            raise BudgetDenied('invalid_budget_configuration') from None

    def reserve(self, kind, model):
        # Unknown rates must not silently enable a more expensive model.
        if model not in ('gpt-4.1-mini', 'text-embedding-3-small'):
            raise BudgetDenied('model_not_budgeted')
        daily, total = self.limits()
        amount = self.RESERVES[kind]
        stamp = datetime.now(timezone.utc).isoformat()
        ident = uuid4().hex
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            used = c.execute('SELECT COALESCE(SUM(reserve_micro_usd),0) FROM v2_ai_calls').fetchone()[0]
            today = c.execute('SELECT COALESCE(SUM(reserve_micro_usd),0) FROM v2_ai_calls WHERE created_at>=?', (stamp[:10],)).fetchone()[0]
            if used + amount > total or today + amount > daily:
                raise BudgetDenied('budget_limit_reached')
            c.execute('INSERT INTO v2_ai_calls VALUES(?,?,?,?,?,?)', (ident, stamp, kind, amount, 'reserved', None))
        return ident

    def finish(self, ident, outcome, usage=None):
        # Only numeric usage, never prompt, source text, user identifier or API key.
        import json
        safe = {k: v for k, v in (usage or {}).items() if k in ('input_tokens', 'output_tokens', 'total_tokens') and type(v) is int}
        with self.db.connect() as c:
            c.execute('UPDATE v2_ai_calls SET outcome=?,usage=? WHERE id=?', (outcome, json.dumps(safe), ident))

    def status(self):
        daily, total = self.limits()
        today = datetime.now(timezone.utc).date().isoformat()
        with self.db.connect() as c:
            used = c.execute('SELECT COALESCE(SUM(reserve_micro_usd),0) FROM v2_ai_calls').fetchone()[0]
            day = c.execute('SELECT COALESCE(SUM(reserve_micro_usd),0) FROM v2_ai_calls WHERE created_at>=?', (today,)).fetchone()[0]
        return {'currency': 'USD', 'accounting': 'conservative_reservations_not_invoice',
                'daily_limit': daily / 1e6, 'total_limit': total / 1e6,
                'daily_reserved': day / 1e6, 'total_reserved': used / 1e6,
                'web_attempt_reserve': .10, 'text_attempt_reserve': .02,
                'scope': 'discovery_conversation_planning_only'}
