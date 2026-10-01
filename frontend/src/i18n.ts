export type Lang = 'bn' | 'en'

export const strings = {
  bn: {
    banner: 'স্যান্ডবক্স - কৃত্রিম ডেটা, কোনো আসল টাকা নয়',
    title: 'সেফঅর্ডার',
    subtitle: 'বিক্রেতার বিশ্বাসযোগ্যতা যাচাই, টাকা আটকে রাখা ও অভিযোগ নিষ্পত্তি',
    toggle: 'English',
  },
  en: {
    banner: 'Sandbox - synthetic data, no real money',
    title: 'SafeOrder',
    subtitle: 'Seller trust check, held payments and dispute resolution',
    toggle: 'বাংলা',
  },
} as const
