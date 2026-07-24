// Rounds a max value up to a "clean" step (1/2/5/10 x a power of ten) and
// returns evenly spaced ticks from 0 to that rounded max -- axis ticks that
// read as 0 / 1,000 / 2,000 rather than 0 / 917 / 1834.
export function niceTicks(max: number, targetCount = 4): number[] {
  if (max <= 0) return [0, 1];

  const rough = max / targetCount;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const residual = rough / magnitude;

  let step: number;
  if (residual > 5) step = 10 * magnitude;
  else if (residual > 2) step = 5 * magnitude;
  else if (residual > 1) step = 2 * magnitude;
  else step = magnitude;

  // The last tick must be >= max -- ceil(max/step) steps, not "while v <=
  // max", which can undershoot by a whole step and leave bars/lines
  // rendering past 100% of their track.
  const count = Math.ceil(max / step);
  const ticks: number[] = [];
  for (let i = 0; i <= count; i++) {
    ticks.push(Math.round(i * step * 100) / 100);
  }
  return ticks;
}
