// Persian/Jalali Date and Number Utilities

// Persian months
const persianMonths = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
]

// Persian weekdays
const persianWeekdays = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه"]

// Convert English numbers to Persian
function toPersianNumbers(str) {
  const persianDigits = "۰۱۲۳۴۵۶۷۸۹"
  const englishDigits = "0123456789"

  return str.toString().replace(/[0-9]/g, (match) => persianDigits[englishDigits.indexOf(match)])
}

// Convert Persian numbers to English
function toEnglishNumbers(str) {
  const persianDigits = "۰۱۲۳۴۵۶۷۸۹"
  const englishDigits = "0123456789"

  return str.toString().replace(/[۰-۹]/g, (match) => englishDigits[persianDigits.indexOf(match)])
}

// Format Persian date
function formatPersianDate(date, format = "YYYY/MM/DD") {
  // This is a simplified version - you would use a proper Persian calendar library
  const year = 1403
  const month = Math.floor(Math.random() * 12) + 1
  const day = Math.floor(Math.random() * 30) + 1

  const formatted = format
    .replace("YYYY", year.toString())
    .replace("MM", month.toString().padStart(2, "0"))
    .replace("DD", day.toString().padStart(2, "0"))

  return toPersianNumbers(formatted)
}

// Get Persian month name
function getPersianMonthName(monthNumber) {
  return persianMonths[monthNumber - 1] || ""
}

// Get Persian weekday name
function getPersianWeekdayName(dayNumber) {
  return persianWeekdays[dayNumber] || ""
}

// Format time in Persian
function formatPersianTime(date) {
  const hours = date.getHours().toString().padStart(2, "0")
  const minutes = date.getMinutes().toString().padStart(2, "0")
  return toPersianNumbers(`${hours}:${minutes}`)
}

// Calculate time difference in Persian
function getTimeDifference(startTime, endTime) {
  const start = new Date(`2000-01-01 ${startTime}`)
  const end = new Date(`2000-01-01 ${endTime}`)
  const diff = end - start

  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

  return toPersianNumbers(`${hours}:${minutes.toString().padStart(2, "0")}`)
}

// Validate Persian date
function isValidPersianDate(dateString) {
  const regex = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/
  const match = dateString.match(regex)

  if (!match) return false

  const year = Number.parseInt(match[1])
  const month = Number.parseInt(match[2])
  const day = Number.parseInt(match[3])

  if (year < 1300 || year > 1500) return false
  if (month < 1 || month > 12) return false
  if (day < 1 || day > 31) return false

  // Check days in month (simplified)
  if (month <= 6 && day > 31) return false
  if (month > 6 && month < 12 && day > 30) return false
  if (month === 12 && day > 29) return false

  return true
}

// Format currency in Persian
function formatPersianCurrency(amount) {
  const formatted = new Intl.NumberFormat("fa-IR").format(amount)
  return `${formatted} ریال`
}

// Export functions
window.PersianUtils = {
  toPersianNumbers,
  toEnglishNumbers,
  formatPersianDate,
  getPersianMonthName,
  getPersianWeekdayName,
  formatPersianTime,
  getTimeDifference,
  isValidPersianDate,
  formatPersianCurrency,
}
