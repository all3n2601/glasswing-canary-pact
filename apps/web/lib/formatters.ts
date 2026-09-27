const compactCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

const wholeNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatCompactCurrency(value: number) {
  return compactCurrency.format(value);
}

export function formatWholeNumber(value: number) {
  return wholeNumber.format(value);
}
