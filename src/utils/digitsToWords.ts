const DIGIT_WORD: Record<string, string> = {
  "0": "zero",
  "1": "one",
  "2": "two",
  "3": "three",
  "4": "four",
  "5": "five",
  "6": "six",
  "7": "seven",
  "8": "eight",
  "9": "nine",
};

/**
 * Replace every digit in the input with its spoken word form.
 * Consecutive digits are separated by spaces.
 * Example: "call 3416 now" → "call three four one six now"
 */
export function digitsToWords(text: string): string {
  return text
    .replace(/\d/g, (d) => ` ${DIGIT_WORD[d]} `)
    .replace(/ {2,}/g, " ")
    .replace(/^ /, "");
}
