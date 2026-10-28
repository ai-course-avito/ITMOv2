export type Airport = { city: string; airport: string; code: string }

// One entry per selectable airport. Keep codes unique across all cities.
export const airports: readonly Airport[] = [
  // Original routes
  { city: 'Москва', airport: 'Шереметьево', code: 'SVO' },
  { city: 'Москва', airport: 'Домодедово', code: 'DME' },
  { city: 'Москва', airport: 'Внуково', code: 'VKO' },
  { city: 'Санкт-Петербург', airport: 'Пулково', code: 'LED' },
  { city: 'Казань', airport: 'Казань', code: 'KZN' },
  { city: 'Сочи', airport: 'Сочи', code: 'AER' },
  // European capitals and airports serving them
  { city: 'Амстердам', airport: 'Схипхол', code: 'AMS' },
  { city: 'Анкара', airport: 'Эсенбога', code: 'ESB' },
  { city: 'Афины', airport: 'Элефтериос Венизелос', code: 'ATH' },
  { city: 'Баку', airport: 'Гейдар Алиев', code: 'GYD' },
  { city: 'Белград', airport: 'Никола Тесла', code: 'BEG' },
  { city: 'Берлин', airport: 'Бранденбург', code: 'BER' },
  { city: 'Берн', airport: 'Берн', code: 'BRN' },
  { city: 'Братислава', airport: 'Братислава', code: 'BTS' },
  { city: 'Брюссель', airport: 'Брюссель', code: 'BRU' },
  { city: 'Будапешт', airport: 'Ференц Лист', code: 'BUD' },
  { city: 'Бухарест', airport: 'Анри Коанда', code: 'OTP' },
  { city: 'Валлетта', airport: 'Мальта', code: 'MLA' },
  { city: 'Варшава', airport: 'Шопена', code: 'WAW' },
  { city: 'Варшава', airport: 'Модлин', code: 'WMI' },
  { city: 'Вена', airport: 'Швехат', code: 'VIE' },
  { city: 'Вильнюс', airport: 'Вильнюс', code: 'VNO' },
  { city: 'Дублин', airport: 'Дублин', code: 'DUB' },
  { city: 'Ереван', airport: 'Звартноц', code: 'EVN' },
  { city: 'Загреб', airport: 'Франьо Туджман', code: 'ZAG' },
  { city: 'Киев', airport: 'Борисполь', code: 'KBP' },
  { city: 'Кишинёв', airport: 'Кишинёв', code: 'RMO' },
  { city: 'Копенгаген', airport: 'Каструп', code: 'CPH' },
  { city: 'Лиссабон', airport: 'Умберту Делгаду', code: 'LIS' },
  { city: 'Лондон', airport: 'Хитроу', code: 'LHR' },
  { city: 'Лондон', airport: 'Гатвик', code: 'LGW' },
  { city: 'Лондон', airport: 'Лондон-Сити', code: 'LCY' },
  { city: 'Лондон', airport: 'Станстед', code: 'STN' },
  { city: 'Лондон', airport: 'Лутон', code: 'LTN' },
  { city: 'Любляна', airport: 'Йоже Пучник', code: 'LJU' },
  { city: 'Люксембург', airport: 'Люксембург', code: 'LUX' },
  { city: 'Мадрид', airport: 'Барахас', code: 'MAD' },
  { city: 'Минск', airport: 'Минск', code: 'MSQ' },
  { city: 'Никосия', airport: 'Ларнака', code: 'LCA' },
  { city: 'Осло', airport: 'Гардермуэн', code: 'OSL' },
  { city: 'Париж', airport: 'Шарль-де-Голль', code: 'CDG' },
  { city: 'Париж', airport: 'Орли', code: 'ORY' },
  { city: 'Подгорица', airport: 'Подгорица', code: 'TGD' },
  { city: 'Прага', airport: 'Вацлав Гавел', code: 'PRG' },
  { city: 'Приштина', airport: 'Приштина', code: 'PRN' },
  { city: 'Рейкьявик', airport: 'Кефлавик', code: 'KEF' },
  { city: 'Рига', airport: 'Рига', code: 'RIX' },
  { city: 'Рим', airport: 'Фьюмичино', code: 'FCO' },
  { city: 'Рим', airport: 'Чампино', code: 'CIA' },
  { city: 'Сараево', airport: 'Сараево', code: 'SJJ' },
  { city: 'Скопье', airport: 'Скопье', code: 'SKP' },
  { city: 'София', airport: 'София', code: 'SOF' },
  { city: 'Стокгольм', airport: 'Арланда', code: 'ARN' },
  { city: 'Стокгольм', airport: 'Бромма', code: 'BMA' },
  { city: 'Таллин', airport: 'Леннарт Мери', code: 'TLL' },
  { city: 'Тбилиси', airport: 'Шота Руставели', code: 'TBS' },
  { city: 'Тирана', airport: 'Мать Тереза', code: 'TIA' },
  { city: 'Хельсинки', airport: 'Вантаа', code: 'HEL' },
]

export function airportLabel(airport: Airport) {
  return `${airport.city} — ${airport.airport}`
}

export function matchingAirports(text: string) {
  const query = text.trim().toLocaleLowerCase('ru-RU')
  return query ? airports.filter(airport => airport.city.toLocaleLowerCase('ru-RU').startsWith(query)) : []
}
