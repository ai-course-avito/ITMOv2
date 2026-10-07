export type RNG = () => number

// default RNG, can be injected/mocked in tests
export const defaultRng: RNG = () => Math.random()
