from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from supply_chain_hub.infrastructure.db.session import get_db_session

DatabaseSession = Annotated[Session, Depends(get_db_session)]
