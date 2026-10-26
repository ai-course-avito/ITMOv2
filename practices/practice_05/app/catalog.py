"""
Каталог продуктов и тематических наборов VkusMart.
Хранит эталонную структуру данных, неизменяемые записи продуктов и темы.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    price: float
    calories: int
    protein: float
    fat: float
    carbs: float
    weight: str
    tags: List[str] = field(default_factory=list)
    allergens: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "calories": self.calories,
            "protein": self.protein,
            "fat": self.fat,
            "carbs": self.carbs,
            "weight": self.weight,
            "tags": list(self.tags),
            "allergens": list(self.allergens),
            "description": self.description,
        }

@dataclass(frozen=True)
class ThemeBundle:
    id: str
    title: str
    description: str
    icon: str
    product_ids: List[str]
    target_budget: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "product_ids": list(self.product_ids),
            "target_budget": self.target_budget
        }

CATEGORIES = [
    "meat_poultry",
    "dairy_eggs",
    "grains_cereals",
    "fish_seafood",
    "vegetables_greens",
    "nuts_snacks",
    "bakery_bread",
    "desserts_sugarfree"
]

ALLERGENS_LIST = ["lactose", "gluten", "nuts", "seafood"]

PRODUCTS: List[Product] = [
    Product(
        id="prod-1",
        name="Филе грудки индейки су-вид",
        category="meat_poultry",
        price=320.0,
        calories=120,
        protein=24.5,
        fat=1.8,
        carbs=0.5,
        weight="250 г",
        tags=["high_protein", "keto", "sugar_free", "gluten_free"],
        allergens=[],
        description="Нежное филе индейки, приготовленное при низкой температуре с пряными травами."
    ),
    Product(
        id="prod-2",
        name="Крупа гречневая ядрица фермерская",
        category="grains_cereals",
        price=85.0,
        calories=313,
        protein=12.6,
        fat=3.3,
        carbs=62.1,
        weight="450 г",
        tags=["budget", "complex_carbs", "gluten_free"],
        allergens=[],
        description="Отборная алтайская гречка, богатая железом и медленными углеводами."
    ),
    Product(
        id="prod-3",
        name="Авокадо Хасс спелое Ready-to-Eat",
        category="vegetables_greens",
        price=210.0,
        calories=160,
        protein=2.0,
        fat=14.7,
        carbs=8.5,
        weight="2 шт",
        tags=["keto", "healthy_fats", "vegan", "sugar_free", "gluten_free"],
        allergens=[],
        description="Мягкое маслянистое авокадо с идеальной кремовой текстурой."
    ),
    Product(
        id="prod-4",
        name="Творог 5% классический ВкусВилл",
        category="dairy_eggs",
        price=125.0,
        calories=121,
        protein=16.0,
        fat=5.0,
        carbs=3.0,
        weight="200 г",
        tags=["high_protein", "sugar_free", "budget"],
        allergens=["lactose"],
        description="Натуральный рассыпчатый творог из цельного и обезжиренного молока."
    ),
    Product(
        id="prod-5",
        name="Форель слабосоленая ломтики",
        category="fish_seafood",
        price=390.0,
        calories=198,
        protein=21.0,
        fat=12.5,
        carbs=0.0,
        weight="150 г",
        tags=["keto", "omega3", "high_protein", "sugar_free", "gluten_free"],
        allergens=["seafood"],
        description="Филе карельской форели деликатного посола с Омега-3 жирными кислотами."
    ),
    Product(
        id="prod-6",
        name="Яйца С0 отборные фермерские",
        category="dairy_eggs",
        price=130.0,
        calories=157,
        protein=12.7,
        fat=11.5,
        carbs=0.7,
        weight="10 шт",
        tags=["budget", "high_protein", "keto", "sugar_free", "gluten_free"],
        allergens=[],
        description="Свежие куриные яйца с ярким желтком от свободного выгула."
    ),
    Product(
        id="prod-7",
        name="Миндаль золотистый сушеный",
        category="nuts_snacks",
        price=240.0,
        calories=579,
        protein=21.2,
        fat=49.9,
        carbs=21.6,
        weight="150 г",
        tags=["keto", "healthy_fats", "vegan", "gluten_free"],
        allergens=["nuts"],
        description="Отборный калифорнийский миндаль без добавления соли и масла."
    ),
    Product(
        id="prod-8",
        name="Батончик протеиновый 'Кокосовый брауни' без сахара",
        category="desserts_sugarfree",
        price=110.0,
        calories=165,
        protein=20.0,
        fat=5.5,
        carbs=4.2,
        weight="60 г",
        tags=["sugar_free", "high_protein", "gluten_free"],
        allergens=["lactose"],
        description="Шоколадно-кокосовый батончик на сывороточном изоляте без сахара."
    ),
    Product(
        id="prod-9",
        name="Хлебцы гречневые хрустящие без глютена",
        category="bakery_bread",
        price=75.0,
        calories=290,
        protein=9.5,
        fat=2.2,
        carbs=58.0,
        weight="100 г",
        tags=["gluten_free", "budget", "vegan"],
        allergens=[],
        description="Легкие хрустящие цельнозерновые хлебцы из 100% гречки."
    ),
    Product(
        id="prod-10",
        name="Молоко миндальное без сахара 1.5%",
        category="dairy_eggs",
        price=185.0,
        calories=35,
        protein=1.0,
        fat=2.5,
        carbs=1.2,
        weight="1 л",
        tags=["lactose_free", "vegan", "sugar_free", "gluten_free", "keto"],
        allergens=["nuts"],
        description="Растительный напиток на основе обжаренного миндаля без лактозы и сахара."
    ),
    Product(
        id="prod-11",
        name="Кефир 2.5% фермерский",
        category="dairy_eggs",
        price=95.0,
        calories=53,
        protein=3.0,
        fat=2.5,
        carbs=4.0,
        weight="900 г",
        tags=["budget", "sugar_free", "gluten_free"],
        allergens=["lactose"],
        description="Традиционный кефир на живых кефирных грибках."
    ),
    Product(
        id="prod-12",
        name="Брокколи на пару с гималайской солью",
        category="vegetables_greens",
        price=145.0,
        calories=34,
        protein=2.8,
        fat=0.4,
        carbs=6.6,
        weight="200 г",
        tags=["keto", "vegan", "sugar_free", "gluten_free", "low_calorie"],
        allergens=[],
        description="Соцветия сочной капусты брокколи шоковой заморозки."
    ),
    Product(
        id="prod-13",
        name="Сыр Пармезан выдержанный 12 мес",
        category="dairy_eggs",
        price=280.0,
        calories=392,
        protein=33.0,
        fat=28.0,
        carbs=0.0,
        weight="150 г",
        tags=["keto", "high_protein", "sugar_free", "gluten_free"],
        allergens=["lactose"],
        description="Твердый пикантный сыр длительного созревания с кристаллами лактата кальция."
    ),
    Product(
        id="prod-14",
        name="Шоколад горький 85% со стевией",
        category="desserts_sugarfree",
        price=190.0,
        calories=540,
        protein=8.5,
        fat=45.0,
        carbs=18.0,
        weight="80 г",
        tags=["sugar_free", "keto", "gluten_free"],
        allergens=[],
        description="Настоящее тертое какао высшего сорта с натуральным подсластителем стевия."
    )
]

THEMES: List[ThemeBundle] = [
    ThemeBundle(
        id="theme-pp",
        title="Здоровый баланс (ПП-рацион)",
        description="Идеальный дневной баланс чистого белка, сложных углеводов и клетчатки.",
        icon="🥗",
        product_ids=["prod-1", "prod-2", "prod-12", "prod-4"],
        target_budget=700.0
    ),
    ThemeBundle(
        id="theme-student",
        title="Студенческий ужин до 500 ₽",
        description="Максимум сытности, белка и питательности при минимальном студенческом бюджете.",
        icon="⚡",
        product_ids=["prod-2", "prod-6", "prod-9", "prod-11"],
        target_budget=400.0
    ),
    ThemeBundle(
        id="theme-keto",
        title="Кето-ланч (High Fat / Low Carb)",
        description="Минимум углеводов, максимум полезных жиров и качественного белка.",
        icon="🥑",
        product_ids=["prod-3", "prod-5", "prod-13"],
        target_budget=900.0
    ),
    ThemeBundle(
        id="theme-sugarfree",
        title="Сладкое без сахара и глютена",
        description="Вкусные десерты и перекусы без скачков инсулина и чувства вины.",
        icon="🍓",
        product_ids=["prod-8", "prod-14", "prod-9"],
        target_budget=400.0
    ),
    ThemeBundle(
        id="theme-office",
        title="Офисный полезный перекус",
        description="Удобно взять с собой в офис: заряд бодрости и сытость без сонливости.",
        icon="💼",
        product_ids=["prod-7", "prod-8", "prod-10"],
        target_budget=550.0
    )
]

PRODUCTS_BY_ID = {p.id: p for p in PRODUCTS}
THEMES_BY_ID = {t.id: t for t in THEMES}
