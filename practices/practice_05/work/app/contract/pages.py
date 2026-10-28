from app.contract.models import Breadcrumb, NavigationLink, Page

_NAVIGATION = (
    NavigationLink(label="Главная", href="/"),
    NavigationLink(label="Ряды Фурье", href="/fourier/"),
    NavigationLink(label="Полиномы Чебышёва", href="/chebyshev/"),
    NavigationLink(label="Теория приближения", href="/approximation/"),
    NavigationLink(label="Демонстрации", href="/demos/"),
    NavigationLink(label="О проекте", href="/about/"),
)


def _page(route: str, topic: str, title: str, description: str, heading: str, sections: list[str]) -> Page:
    breadcrumb = [] if route == "/" else [Breadcrumb(label="Главная", href="/")]
    return Page(
        route=route,
        topic=topic,
        title=title,
        description=description,
        heading=heading,
        sections=sections,
        canonical=route,
        breadcrumb=breadcrumb,
        navigation=list(_NAVIGATION),
    )


PAGES = {
    "/": _page("/", "home", "Математика приближений", "Образовательный сайт о рядах Фурье и полиномах Чебышёва.", "Математика приближений", ["hero", "features", "highlights", "demos", "cta"]),
    "/fourier/": _page("/fourier/", "fourier-series", "Ряды Фурье | Математика приближений", "Интуитивное объяснение рядов Фурье и частичных сумм.", "Ряды Фурье", ["hero", "features", "highlights", "demos", "cta"]),
    "/chebyshev/": _page("/chebyshev/", "chebyshev-polynomials", "Полиномы Чебышёва | Математика приближений", "Определение, ортогональность и узлы полиномов Чебышёва.", "Полиномы Чебышёва", ["hero", "features", "highlights", "demos", "cta"]),
    "/approximation/": _page("/approximation/", "approximation-theory", "Теория приближения | Математика приближений", "Интерполяция, ошибки и устойчивость численных методов.", "Теория приближения", ["hero", "features", "highlights", "demos", "cta"]),
    "/demos/": _page("/demos/", "demonstrations", "Демонстрации | Математика приближений", "Интерактивные демонстрации рядов Фурье и полиномов Чебышёва.", "Демонстрации", ["hero", "demos", "cta"]),
    "/about/": _page("/about/", "about", "О проекте | Математика приближений", "Методология и доступность образовательного сайта.", "О проекте", ["hero", "features", "highlights", "cta"]),
}


def page_contract(route: str) -> Page:
    return PAGES[route]
