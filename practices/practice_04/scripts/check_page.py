"""Static contract checks for the Olympiad Start landing.

Usage: python3 scripts/check_page.py [project_dir]
Exits 1 if any check fails. Standard library only.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "source", "track", "wbr"}

PROGRAMS = [
  ("Старт", "5–6 класс", "4900 ₽"),
  ("Основа", "7–8 класс", "5900 ₽"),
  ("Интенсив", "9 класс", "6900 ₽"),
]


class Node:
  def __init__(self, tag, attrs, parent=None):
    self.tag = tag
    self.attrs = dict(attrs)
    self.parent = parent
    self.children = []
    self.text_parts = []

  @property
  def classes(self):
    return self.attrs.get("class", "").split()

  def text(self):
    parts = list(self.text_parts)
    for child in self.children:
      parts.append(child.text())
    return re.sub(r"\s+", " ", " ".join(parts)).strip()

  def walk(self):
    for child in self.children:
      yield child
      yield from child.walk()

  def find_all(self, tag=None, cls=None):
    return [n for n in self.walk()
            if (tag is None or n.tag == tag) and (cls is None or cls in n.classes)]

  def by_id(self, node_id):
    return next((n for n in self.walk() if n.attrs.get("id") == node_id), None)


class TreeBuilder(HTMLParser):
  def __init__(self):
    super().__init__(convert_charrefs=True)
    self.root = Node("#root", [])
    self.current = self.root

  def handle_starttag(self, tag, attrs):
    node = Node(tag, attrs, self.current)
    self.current.children.append(node)
    if tag not in VOID_TAGS:
      self.current = node

  def handle_startendtag(self, tag, attrs):
    self.current.children.append(Node(tag, attrs, self.current))

  def handle_endtag(self, tag):
    node = self.current
    while node is not self.root and node.tag != tag:
      node = node.parent
    if node is not self.root:
      self.current = node.parent

  def handle_data(self, data):
    self.current.text_parts.append(data)


def check(project_dir):
  results = []

  def expect(ok, label):
    results.append((bool(ok), label))

  html_path = project_dir / "index.html"
  css_path = project_dir / "styles.css"
  if not html_path.exists() or not css_path.exists():
    return [(False, "index.html and styles.css exist")]

  html = html_path.read_text(encoding="utf-8")
  css = css_path.read_text(encoding="utf-8")
  builder = TreeBuilder()
  builder.feed(html)
  doc = builder.root

  # Structure
  for tag in ("header", "nav", "main", "footer"):
    expect(len(doc.find_all(tag)) == 1, f"exactly one <{tag}>")
  expect(len(doc.find_all("h1")) == 1, "exactly one <h1>")
  levels = [int(n.tag[1]) for n in doc.walk() if re.fullmatch(r"h[1-6]", n.tag)]
  skipped = [b for a, b in zip(levels, levels[1:]) if b > a + 1]
  expect(not skipped, "heading levels do not skip")

  sections = doc.find_all("section")
  ids = [n.attrs["id"] for n in doc.walk() if "id" in n.attrs]
  expect(all("id" in s.attrs for s in sections), "every <section> has an id")
  expect(len(ids) == len(set(ids)), "ids are unique")

  anchors = [n.attrs["href"][1:] for n in doc.find_all("a")
             if n.attrs.get("href", "").startswith("#") and len(n.attrs["href"]) > 1]
  broken = sorted({a for a in anchors if a not in ids})
  expect(not broken, "every #anchor has a target" + (f" (missing: {', '.join(broken)})" if broken else ""))

  # Feature A contract
  header = doc.find_all("header")
  header_text = header[0].text() if header else ""
  expect("Olympiad Start" in header_text, "header has Olympiad Start wordmark")
  expect(any(a.text() == "Записаться" for a in (header[0].find_all("a") if header else [])),
         "header has «Записаться» CTA")

  hero = doc.by_id("hero")
  hero_links = [a.attrs.get("href") for a in hero.find_all("a")] if hero else []
  expect("#programs" in hero_links and "#how" in hero_links, "hero CTAs link to #programs and #how")

  expect(len(doc.find_all(cls="benefit")) == 3, "exactly 3 benefits")
  audience = doc.by_id("audience")
  expect(audience is not None and "5–9" in audience.text(), "«Для кого» mentions grades 5–9")

  cards = doc.find_all(cls="program-card")
  expect(len(cards) == 3, "exactly 3 program cards")
  for card, (name, grade, price) in zip(cards, PROGRAMS):
    text = card.text()
    expect(name in text and grade in text and price in text, f"program {name}: {grade}, {price}")
    expect(card.find_all(cls="program-card__topics") and card.find_all(cls="program-card__format"),
           f"program {name} has topics and format")

  how = doc.by_id("how")
  expect(how is not None and len(how.find_all(cls="step")) == 3, "exactly 3 steps in #how")

  coaches = doc.find_all(cls="coach-card")
  expect(len(coaches) == 3, "exactly 3 coach cards")
  expect(all(c.find_all("svg") for c in coaches), "every coach has an SVG avatar")

  faq = doc.by_id("faq")
  details = faq.find_all("details") if faq else []
  expect(len(details) == 4, "exactly 4 FAQ <details>")
  expect(all(d.children and d.children[0].tag == "summary" for d in details),
         "every FAQ item starts with <summary>")

  expect(any(a.attrs.get("href") == "#signup" for a in doc.find_all("a")), "a CTA links to #signup")

  # Feature B contract
  results.extend(check_signup(doc, cards, project_dir))

  # Stack and content rules
  expect(not doc.find_all("img"), "no <img> (illustrations are inline SVG)")
  svgs = doc.find_all("svg")
  expect(all(s.attrs.get("aria-hidden") == "true" for s in svgs), "decorative SVGs have aria-hidden=\"true\"")

  external = [n.attrs.get(attr) for n in doc.walk() for attr in ("src", "href")
              if re.match(r"(https?:)?//", n.attrs.get(attr, ""))]
  css_external = re.findall(r"@import|url\(\s*['\"]?(?:https?:)?//", css)
  expect(not external and not css_external, "no external resources (CDNs, fonts, images)")

  scripts = [s.attrs.get("src") for s in doc.find_all("script") if s.attrs.get("src")]
  expect(all(src == "script.js" for src in scripts), "only script.js is loaded as a script")
  if scripts:
    expect((project_dir / "script.js").exists(), "script.js exists")

  css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
  expect(css_no_comments.count("{") == css_no_comments.count("}"), "styles.css braces are balanced")
  expect(":root" in css, "styles.css defines :root custom properties")
  outside_root = re.sub(r":root\s*\{[^}]*\}", "", css_no_comments)
  raw_hex = sorted(set(re.findall(r"#[0-9a-fA-F]{3,8}\b", outside_root)))
  expect(not raw_hex, "no raw hex colors outside :root (style guide rule 2)"
         + (f" (found: {', '.join(raw_hex)})" if raw_hex else ""))

  return results


SIGNUP_PROGRAMS = [
  # (option value, name, monthly price, grades)
  ("start", "Старт", "4900", "5 6"),
  ("base", "Основа", "5900", "7 8"),
  ("intensive", "Интенсив", "6900", "9"),
]


def check_signup(doc, cards, project_dir):
  """Static contract for Feature B. Behaviour (prices, errors, focus) needs a browser."""
  results = []

  def expect(ok, label):
    results.append((bool(ok), label))

  signups = [n for n in doc.walk() if n.attrs.get("id") == "signup"]
  expect(len(signups) == 1 and signups[0].tag == "section", "exactly one <section id=\"signup\">")
  if not signups:
    return results
  signup = signups[0]

  forms = signup.find_all("form")
  expect(len(forms) == 1, "#signup has one <form>")
  if not forms:
    return results
  form = forms[0]
  expect("action" not in form.attrs, "sign-up form has no action (no network request)")

  ids = {n.attrs["id"]: n for n in doc.walk() if "id" in n.attrs}
  labelled = {n.attrs.get("for") for n in form.find_all("label")}

  def field(name):
    return [n for n in form.walk() if n.tag in ("input", "select") and n.attrs.get("name") == name]

  def described(node):
    refs = node.attrs.get("aria-describedby", "").split()
    return any(ref in ids and "error" in ids[ref].attrs.get("id", "") for ref in refs)

  program = field("program")
  expect(len(program) == 1 and program[0].tag == "select", "program is a <select>")
  options = [o for o in (program[0].find_all("option") if program else []) if o.attrs.get("value")]
  expect([(o.attrs["value"], o.attrs.get("data-price"), o.attrs.get("data-grades")) for o in options]
         == [(v, p, g) for v, _, p, g in SIGNUP_PROGRAMS],
         "program options: Старт 4900 (5–6), Основа 5900 (7–8), Интенсив 6900 (9)")
  expect(all(name in o.text() for o, (_, name, _, _) in zip(options, SIGNUP_PROGRAMS)),
         "program options are named Старт / Основа / Интенсив")
  expect(program and "selected" in next((o.attrs for o in program[0].find_all("option")
                                         if o.attrs.get("value") == ""), {}),
         "no program is preselected by default")

  grade = field("grade")
  expect(len(grade) == 1 and grade[0].tag == "select", "grade is a <select>")
  grades = [o.attrs.get("value") for o in (grade[0].find_all("option") if grade else []) if o.attrs.get("value")]
  expect(grades == ["5", "6", "7", "8", "9"], "grade options are 5–9")

  duration = field("duration")
  expect(sorted(n.attrs.get("value") for n in duration) == ["1", "3", "6"]
         and all(n.attrs.get("type") == "radio" for n in duration),
         "duration is radios 1 / 3 / 6 months")
  expect([n.attrs.get("value") for n in duration if "checked" in n.attrs] == ["1"],
         "duration defaults to 1 month")

  name = field("parent_name")
  email = field("email")
  consent = field("consent")
  expect(len(name) == 1, "parent's name field")
  expect(len(email) == 1 and email[0].attrs.get("type") == "email", "parent's email is type=\"email\"")
  expect(len(consent) == 1 and consent[0].attrs.get("type") == "checkbox", "consent checkbox")

  controls = program + grade + name + email + consent
  expect(controls and all("required" in n.attrs for n in controls + duration[:1]), "all fields are required")
  expect(all(n.attrs.get("id") in labelled for n in controls + duration), "every field has a <label for>")
  expect(all(described(n) for n in controls), "every field has an error element via aria-describedby")

  for key in ("monthly", "discount", "total"):
    node = ids.get(f"signup-{key}")
    expect(node is not None and node.text() == "—", f"#signup-{key} shows «—» before a program is chosen")
  hint = ids.get("signup-price-hint")
  expect(hint is not None and hint.text() == "Выберите программу", "price hint «Выберите программу»")

  expect(any(b.attrs.get("type") == "submit" for b in form.find_all("button")), "form has a submit button")

  picks = [[a for a in card.find_all("a") if a.text() == "Выбрать"] for card in cards]
  expect(len(cards) == 3 and all(len(p) == 1 for p in picks), "every program card has one «Выбрать» link")
  expect([p[0].attrs.get("href") for p in picks if p] == ["#signup"] * 3, "«Выбрать» links go to #signup")
  expect([p[0].attrs.get("data-program") for p in picks if p] == [v for v, *_ in SIGNUP_PROGRAMS],
         "«Выбрать» links preselect their own program")

  expect(any(s.attrs.get("src") == "script.js" for s in doc.find_all("script")), "index.html loads script.js")
  js_path = project_dir / "script.js"
  js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""
  expect(js and not re.search(r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|\.submit\s*\(", js),
         "script.js sends no network requests")
  return results


def main():
  project_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
  results = check(project_dir)
  failed = [label for ok, label in results if not ok]
  for ok, label in results:
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
  print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
  sys.exit(1 if failed else 0)


if __name__ == "__main__":
  main()
