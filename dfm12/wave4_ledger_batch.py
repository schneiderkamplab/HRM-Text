"""CPU-tested bounded group-commit primitive; not installed into live runtime."""
from contextlib import contextmanager
import copy


class NestedConnection:
    """Preserve existing per-operation transactions as savepoints in one batch."""
    def __init__(self, connection):
        self.connection = connection
        self.stack = []
        self.sequence = 0

    def execute(self, sql, parameters=()):
        statement = sql.strip().upper()
        if statement in ('BEGIN IMMEDIATE', 'BEGIN'):
            name = 'w4_batch_' + str(self.sequence)
            self.sequence += 1
            self.stack.append(name)
            return self.connection.execute('SAVEPOINT '+name)
        if statement == 'COMMIT':
            return self.commit()
        if statement == 'ROLLBACK':
            return self.rollback()
        return self.connection.execute(sql, parameters)

    def commit(self):
        if not self.stack:
            raise ValueError('Unexpected inner commit without savepoint')
        return self.connection.execute('RELEASE SAVEPOINT '+self.stack.pop())

    def rollback(self):
        if not self.stack:
            raise ValueError('Unexpected inner rollback without savepoint')
        name = self.stack.pop()
        self.connection.execute('ROLLBACK TO SAVEPOINT '+name)
        return self.connection.execute('RELEASE SAVEPOINT '+name)

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.commit()
        else:
            self.rollback()

    def __getattr__(self, name):
        return getattr(self.connection, name)


def execute_batch(ledger, provider, operations, max_batch=16):
    """Owner-thread only. Return results only after BOTH durable commits.

    A source-commit/ledger-commit crash can leave retained source selections, as
    in the original per-row ordering. It must never expose uncommitted ledger
    allocations or rewind source cursors. This primitive does not schedule work.
    """
    if not operations or len(operations)>max_batch or max_batch not in (8,16,32):
        raise ValueError('Explicit bounded nonempty batch required')
    db=ledger.db
    source=provider.db if provider is not None else None
    if db.in_transaction or (source is not None and source.in_transaction):
        raise ValueError('Existing transaction cannot enter group commit')
    if source is db:
        raise ValueError('Expected separate source and ledger databases')
    snapshots={name:copy.deepcopy(getattr(ledger,name)) for name in
               ('allocated_groups','group_snapshot') if hasattr(ledger,name)}
    source_committed=False
    publish=getattr(ledger,'publish',None)
    if publish is not None:
        ledger.publish=lambda:None  # Never publish uncommitted quota hints.
    try:
        if source is not None:
            source.execute('BEGIN IMMEDIATE')
            provider.db=NestedConnection(source)
        db.execute('BEGIN IMMEDIATE')
        ledger.db=NestedConnection(db)
        results=[operation() for operation in operations]
        if ledger.db.stack or (source is not None and provider.db.stack):
            raise ValueError('Unclosed nested transaction')
        # Do not reverse this order: a ledger allocation must have durable source lineage.
        if source is not None:
            source.commit();source_committed=True
        db.commit()
        return results
    except BaseException:
        if db.in_transaction:db.rollback()
        if source is not None and not source_committed and source.in_transaction:source.rollback()
        for name,value in snapshots.items():setattr(ledger,name,value)
        raise
    finally:
        ledger.db=db
        if provider is not None:provider.db=source
        if publish is not None:ledger.publish=publish
        if hasattr(ledger,'refresh'):ledger.refresh()
