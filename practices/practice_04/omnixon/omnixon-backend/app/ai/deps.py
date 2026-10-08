from dataclasses import dataclass
from database import PostgresDB


@dataclass
class Dependencies:
    db: PostgresDB
