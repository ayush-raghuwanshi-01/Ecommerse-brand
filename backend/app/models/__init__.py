"""Import every model so Alembic autogenerate and Base.metadata see them all."""

from app.models import (  # noqa: F401
    cart,
    catalog,
    commerce,
    inventory,
    order,
    payment,
    returns,
    user,
)
