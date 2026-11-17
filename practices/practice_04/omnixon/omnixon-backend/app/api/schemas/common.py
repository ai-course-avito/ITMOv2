from typing import Annotated

from pydantic import StringConstraints

from domain.entities import NAME_MAX

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)]
