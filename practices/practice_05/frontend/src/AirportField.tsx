import { useId, useState, type KeyboardEvent } from 'react'
import { airportLabel, matchingAirports, type Airport } from './airports'

export type AirportValue = { text: string; selected: Airport | null }

type Props = {
  label: string
  value: AirportValue
  error: string
  onChange: (value: AirportValue) => void
}

export function AirportField({ label, value, error, onChange }: Props) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const suggestions = matchingAirports(value.selected ? value.selected.city : value.text)
  const showList = open && value.text.trim().length > 0

  function choose(airport: Airport) {
    onChange({ text: airportLabel(airport), selected: airport })
    setOpen(false)
    setActive(-1)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      setActive(-1)
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!value.text.trim()) return
      event.preventDefault()
      setOpen(true)
      if (suggestions.length) {
        setActive(previous => event.key === 'ArrowDown'
          ? (previous + 1) % suggestions.length
          : (previous + suggestions.length) % suggestions.length)
      }
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      if (showList && active >= 0 && suggestions[active]) choose(suggestions[active])
    }
  }

  return (
    <div className="field airport-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={`${id}-list`}
        aria-activedescendant={showList && active >= 0 ? `${id}-option-${active}` : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        value={value.text}
        placeholder="Введите город"
        onChange={event => {
          if (event.target.value === value.text) return
          onChange({ text: event.target.value, selected: null })
          setActive(-1)
          setOpen(Boolean(event.target.value.trim()))
        }}
        onFocus={() => setOpen(Boolean(value.text.trim()))}
        onBlur={() => { setOpen(false); setActive(-1) }}
        onKeyDown={handleKeyDown}
      />
      {showList && <div id={`${id}-list`} className="airport-list" role="listbox" aria-label={`${label}: аэропорты`}>
        {suggestions.length ? suggestions.map((airport, index) => (
          <button
            id={`${id}-option-${index}`}
            className={`airport-option${index === active ? ' active' : ''}`}
            role="option"
            aria-selected={index === active}
            type="button"
            key={airport.code}
            onPointerDown={event => { event.preventDefault(); choose(airport) }}
            onClick={() => choose(airport)}
          >{airportLabel(airport)}</button>
        )) : <p className="airport-empty">Аэропорты не найдены</p>}
      </div>}
      {error && <p id={`${id}-error`} className="field-error">{error}</p>}
    </div>
  )
}
