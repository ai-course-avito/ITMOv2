from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field


def create_app() -> FastAPI:
    app = FastAPI(title="Coffee Backend", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        return {"ready": True}

    # Reserve /api base and mount v1 router
    api_router = APIRouter(prefix="/api")
    v1_router = APIRouter(prefix="/v1")

    @v1_router.get("/")
    def v1_root():
        return {"service": "coffee-backend", "version": "v1"}

    api_router.include_router(v1_router)
    app.include_router(api_router)

    # Mount static frontend at /ui
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")

        @app.get("/")
        def root_redirect():
            # Redirect base URL to UI
            return RedirectResponse(url="/ui/")

    return app


# --- Menu management (in-memory) ---

class MenuItemIn(BaseModel):
    name: str = Field(min_length=1)
    ingredients: List[str] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list)
    priceCoffeeCoin: float = Field(gt=0)


class MenuItem(MenuItemIn):
    id: int


class MenuRepo:
    def __init__(self) -> None:
        self._items: dict[int, MenuItem] = {}
        self._next_id: int = 1

    def list(self) -> List[MenuItem]:
        return list(self._items.values())

    def create(self, data: MenuItemIn) -> MenuItem:
        mid = self._next_id
        self._next_id += 1
        item = MenuItem(id=mid, **data.model_dump())
        self._items[mid] = item
        return item

    def get(self, mid: int) -> Optional[MenuItem]:
        return self._items.get(mid)

    def update(self, mid: int, data: MenuItemIn) -> MenuItem:
        if mid not in self._items:
            raise KeyError
        item = MenuItem(id=mid, **data.model_dump())
        self._items[mid] = item
        return item

    def delete(self, mid: int) -> None:
        if mid not in self._items:
            raise KeyError
        del self._items[mid]


repo = MenuRepo()


def mount_menu_api(app: FastAPI) -> None:
    menu = APIRouter(prefix="/api/v1/menu", tags=["menu"])

    @menu.get("/", response_model=List[MenuItem])
    def list_menu():
        return repo.list()

    @menu.post("/", status_code=status.HTTP_201_CREATED, response_model=MenuItem)
    def create_menu(item: MenuItemIn):
        return repo.create(item)

    @menu.get("/{mid}", response_model=MenuItem)
    def get_menu(mid: int):
        found = repo.get(mid)
        if not found:
            raise HTTPException(status_code=404, detail="Menu item not found")
        return found

    @menu.put("/{mid}", response_model=MenuItem)
    def update_menu(mid: int, item: MenuItemIn):
        try:
            return repo.update(mid, item)
        except KeyError:
            raise HTTPException(status_code=404, detail="Menu item not found")

    @menu.delete("/{mid}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_menu(mid: int):
        try:
            repo.delete(mid)
        except KeyError:
            raise HTTPException(status_code=404, detail="Menu item not found")

    app.include_router(menu)


# Mount menu API after app creation
mount_menu_api(app)


app = create_app()
