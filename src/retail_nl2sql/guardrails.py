"""Parse and allow-list generated SQL before it reaches SQLite."""

from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class QueryRejected(ValueError):
    """Raised when generated SQL is not an allowed single read-only query."""


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    referenced_tables: frozenset[str]


_FORBIDDEN_NODES = (
    exp.Alter,
    exp.Attach,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Detach,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Transaction,
    exp.Update,
)


def validate_read_only_query(sql: str, allowed_tables: frozenset[str]) -> ValidatedQuery:
    candidate = sql.strip()
    if not candidate:
        raise QueryRejected("The model returned an empty query")

    try:
        statements = [statement for statement in parse(candidate, read="sqlite") if statement]
    except ParseError as error:
        raise QueryRejected(f"SQL could not be parsed: {error}") from error

    if len(statements) != 1:
        raise QueryRejected("Exactly one SQL statement is allowed")

    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise QueryRejected("Only SELECT queries are allowed")
    if any(statement.find(node_type) is not None for node_type in _FORBIDDEN_NODES):
        raise QueryRejected("The query contains a non-read-only operation")

    cte_names = {cte.alias_or_name.casefold() for cte in statement.find_all(exp.CTE)}
    referenced = {
        table.name.casefold()
        for table in statement.find_all(exp.Table)
        if table.name and table.name.casefold() not in cte_names
    }
    unknown = referenced - {name.casefold() for name in allowed_tables}
    if unknown:
        raise QueryRejected(f"Query references tables outside the allow-list: {sorted(unknown)}")

    normalized = statement.sql(dialect="sqlite", pretty=True)
    return ValidatedQuery(sql=normalized, referenced_tables=frozenset(referenced))
