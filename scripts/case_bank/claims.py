"""Buyer claims by family, written by the assistant (not by a ChatGPT/Gemini run, not by the team).

Each family is a list of (style, text) where style is standard | banglish | regional | mixed.
Placeholders: {p} product, {amt} amount in taka, {d} days. The position in the list decides which
split may use a text (see ``scripts/make_cases.py``): the last seven of sixteen are held out, so a
test claim never appears in training. The Bangla (especially "regional") needs native review.
"""

NOT_RECEIVED = [
    ("standard", "আমি টাকা দিয়ে {p} অর্ডার করেছিলাম কিন্তু এখনো কোনো পার্সেল হাতে পাইনি।"),
    ("banglish", "ami {p} order korsilam, taka dilam, kintu parcel ekhono pai nai."),
    ("regional", "{p} অর্ডার করছিলাম, টাকাও দিছি, পার্সেল তো আমার হাতে আহে নাই।"),
    ("mixed", "আমি {p} order করেছি, payment complete, কিন্তু parcel receive করিনি।"),
    ("standard", "অর্ডার করার পর {d} দিন পার হয়ে গেছে, আমি পণ্য বুঝে পাইনি। আমার টাকা আটকে আছে।"),
    ("banglish", "vai amar {p} ta ekhono pailam na, taka ferot chai."),
    ("standard", "আমার পার্সেলটি আমি গ্রহণ করিনি, কোনো ডেলিভারি আমার কাছে আসেনি।"),
    (
        "mixed",
        "Sir, amar order er parcel ashe nai, tracking e ki dekhay bujhtesi na, refund dite hobe.",
    ),
    ("regional", "ভাই {p} এর পার্সেল আমার বাসায় আহে নাই, টেহা ফেরত দেন।"),
    ("banglish", "parcel er kono khobor nai, {p} ta paini, ki hocche bolen."),
    ("regional", "{p} আইজও পাইলাম না, কী অইল কন তো?"),
    ("standard", "আমি এখনো আমার অর্ডারের পণ্যটি পাইনি। দয়া করে বিষয়টি দেখুন।"),
    ("mixed", "Order confirm হয়েছে but product হাতে পাই নাই, আমার {amt} টাকা hold এ আছে।"),
    ("banglish", "taka dilam {p} er jonno, ekhono kichu hate pai nai."),
    ("standard", "পণ্যটি আমি হাতে পাইনি, অথচ আমাকে বলা হচ্ছে ডেলিভারি হয়ে গেছে।"),
    ("regional", "অর্ডার দিছিলাম, জিনিস আইলো না, টাকা ফেরত চাই।"),
]

WRONG_ITEM = [
    ("standard", "আমি {p} অর্ডার করেছিলাম কিন্তু আমাকে সম্পূর্ণ অন্য একটি জিনিস পাঠানো হয়েছে।"),
    ("banglish", "ami {p} order korsilam, kintu onno jinish pathaise, ei product ta amar na."),
    ("regional", "{p} চাইছিলাম, আর দিছে অন্য জিনিস, এইডা তো আমার অর্ডার না।"),
    ("mixed", "আমি যেটা order করেছি সেটা আসেনি, একদম different একটা item এসেছে।"),
    ("standard", "পার্সেল খুলে দেখি ভেতরে আমার অর্ডার করা পণ্য নেই, অন্য কিছু আছে।"),
    ("banglish", "original bole {p} dise, kintu eta toh fake mone hocche, brand er logo thik na."),
    ("standard", "আমাকে নকল পণ্য দেওয়া হয়েছে, আসলটার দাম নিয়েছে অথচ মান একদম নিম্নমানের।"),
    ("mixed", "Box e jeta ashche seta amar order kora model na, color o size o alada."),
    ("regional", "আমারে ভুল জিনিস পাঠাইছে, টেহা দিছি এক জিনিসের আর আইছে আরেক জিনিস।"),
    ("banglish", "vul product pathaise vai, amar order ar eta mile na, ferot nibe naki?"),
    ("regional", "{p} এর জায়গায় অন্য জিনিস আইছে, এইডা লমু না।"),
    ("standard", "যে মডেলের দাম দিয়েছি তার বদলে পুরোনো মডেল পাঠানো হয়েছে।"),
    ("mixed", "Product ta original na, packaging e spelling mistake ache, fake mone hocche."),
    ("banglish", "onno rongo er {p} pathaise, ami ta chai nai, taka ferot chai."),
    ("standard", "অর্ডারে যা লেখা ছিল তার সাথে হাতে পাওয়া জিনিসের কোনো মিল নেই, এটা ভুল পণ্য।"),
    ("regional", "জিনিসটা আমার না, ভুল পাঠাইছে, বদলাইয়া দেন নাইলে টাকা দেন।"),
]

DAMAGED = [
    ("standard", "পার্সেল খুলে দেখি {p} ভাঙা অবস্থায় এসেছে। আমি এটি ব্যবহার করতে পারছি না।"),
    ("banglish", "{p} ta vanga obosthay esheche, use kora jacche na, taka ferot chai."),
    ("regional", "{p} ভাঙ্গা আইছে, একদম নষ্ট, এই জিনিস দিয়া কী করমু?"),
    ("mixed", "Product এ defect আছে, কাজ করছে না, একদম dead।"),
    ("standard", "পণ্যটি ত্রুটিপূর্ণ, প্রথম দিনেই কাজ করা বন্ধ হয়ে গেছে।"),
    ("banglish", "box e kharap hoye gese, vitorer jinish crack kora, ei obosthay ni na."),
    ("standard", "প্যাকেট ছেঁড়া ছিল এবং ভেতরের পণ্য দুমড়ে-মুচড়ে গেছে, আমি ক্ষতিপূরণ চাই।"),
    ("mixed", "Screen e crack ache, packaging khub dhillah, amar refund chai."),
    ("regional", "জিনিসটা ফাইট্টা গেছে, ডিব্বার ভিতরেই ভাঙ্গা, টেহা ফেরত দেন।"),
    ("banglish", "ekdom nosto jinish diyese, chalu e hocche na."),
    ("regional", "{p} চালু অয় না, কাম করে না, খারাপ জিনিস দিছে।"),
    ("standard", "পণ্যের একটি অংশ ভেঙে আলাদা হয়ে এসেছে, এটি কোনোভাবেই ব্যবহারযোগ্য নয়।"),
    ("mixed", "Delivery এর সময় দেখলাম box টা পুরো চাপা, ভেতরে product damaged।"),
    ("banglish", "joto ta bhebechilam tar theke onek kharap obosthay {p} elo."),
    ("standard", "আমি পণ্যটি খুলে দেখি এতে দাগ ও ফাটল রয়েছে, ভালো অবস্থায় আসেনি।"),
    ("regional", "জিনিসে সমস্যা আছে, ঠিকমতো কাম করে না, ফেরত নিয়া টেহা দেন।"),
]

NOT_AS_DESCRIBED = [
    ("standard", "পোস্টে যা দেখানো হয়েছিল পণ্যটি তার সাথে মেলে না, সাইজ ও রং আলাদা।"),
    ("banglish", "post e jemon dekhaise {p} ta ekdom onno rokom, size choto."),
    ("regional", "ছবিতে যেমন দেখাইছিল, জিনিসটা ওইরকম না, মান কম।"),
    ("mixed", "Listing এ বলা ছিল premium quality, কিন্তু যেটা পেলাম সেটা একেবারে cheap material।"),
    ("standard", "কাপড়ের মান লিস্টিংয়ের বর্ণনার তুলনায় অনেক নিম্নমানের, রংও ফিকে।"),
    ("banglish", "size L bolsilo, ashole M er moto hoise, description er sathe mile na."),
    ("standard", "বর্ণনায় লেখা ছিল পণ্যটি জলরোধী, কিন্তু পানি লাগতেই নষ্ট হয়ে গেছে।"),
    ("mixed", "Photo te color ta deep blue chilo but এখন যেটা এসেছে সেটা light sky blue।"),
    ("regional", "যেই মাপ কইছিল ওই মাপ না, জিনিসটা অনেক ছোড, লাগে না।"),
    ("banglish", "advertise er sathe quality mile na, ami eta expect kori nai."),
    ("regional", "বিজ্ঞাপনে যা কইছে তার লগে জিনিসের কোনো মিল নাই।"),
    ("standard", "পণ্যের ব্র্যান্ড ও মডেল বর্ণনার সাথে সম্পূর্ণ মেলে না।"),
    ("mixed", "Description e ছিল 6 months warranty, এখন বলছে warranty নেই, এটা misleading।"),
    ("banglish", "chobi ar jinish ek na, ei price e eto kharap quality ashha korini."),
    ("standard", "আমাকে যে ডিজাইনটি দেখিয়ে বিক্রি করা হয়েছে, পাঠানো পণ্যটির নকশা সম্পূর্ণ ভিন্ন।"),
    ("regional", "দেখাইছে এক রকম, দিছে আরেক রকম, এমন করলে হইব?"),
]

WANT_REFUND = [
    ("standard", "আমি পণ্যটি ফেরত দিতে চাই, আমার টাকা ফেরত দিন।"),
    ("banglish", "{p} ta amar ar lagbe na, refund diye den."),
    ("regional", "জিনিসটা আর লাগব না, ফেরত নিয়া টেহা দিয়া দেন।"),
    ("mixed", "আমার mind change হয়েছে, product ফেরত দিতে চাই, money back please।"),
    ("standard", "পণ্যটি আমার পছন্দ হয়নি, আমি রিফান্ড চাই।"),
    ("banglish", "pochondo hoy nai, ferot nen ar taka din."),
    ("standard", "আমার এই পণ্যটির প্রয়োজন নেই, দয়া করে অর্ডার বাতিল করে টাকা ফেরত দিন।"),
    ("mixed", "Product ta fit korse na, size ঠিক হয়নি, return করতে চাই।"),
    ("regional", "জিনিসটা মনে ধরে নাই, ফেরত লন, টেহা চাই।"),
    ("banglish", "onno jaigay er theke shosta dekhlam, ferot nite parben?"),
    ("regional", "আমার আর এই জিনিস লাগব না, বদলাইয়া বা ফেরত দেন।"),
    ("standard", "আমি এই অর্ডারটি বাতিল করতে চাই এবং পুরো টাকা ফেরত পেতে চাই।"),
    ("mixed", "Gift দিতে চেয়েছিলাম কিন্তু এখন আর দরকার নেই, refund করে দিন।"),
    ("banglish", "taka ferot dite hobe, ami ar eta rakhte chai na."),
    ("standard", "অর্ডার দেওয়ার পর আমার সিদ্ধান্ত বদলেছে, আমি পণ্য ফেরত পাঠাতে চাই।"),
    ("regional", "না লাগলে ফেরত দেওনের কথা আছিল, আমারে টেহা দেন।"),
]

THREAT = [
    ("standard", "পণ্যে সমস্যা আছে, দাম অর্ধেক না করলে আমি আপনার পেজে খারাপ রিভিউ দেব।"),
    ("banglish", "taka na dile page e kharap review dibo, report korbo, dekhe nibo."),
    ("regional", "টেহা ফেরত না দিলে পেজ রিপোর্ট করমু, সবাইরে জানাইয়া দিমু।"),
    (
        "mixed",
        "আমাকে ৫০% discount দাও, otherwise fake seller bole post korbo, tomar page nosto hobe।",
    ),
    ("standard", "এখনই টাকা ফেরত দিন, নইলে আমি আইনি ব্যবস্থা নেব এবং সবাইকে জানিয়ে দেব।"),
    ("banglish", "refund dao na hole facebook e sob bole dibo, tomar business shesh."),
    ("standard", "দাম কমিয়ে না দিলে আমি আপনাদের বিরুদ্ধে অভিযোগ করব এবং পেজ বন্ধ করিয়ে দেব।"),
    ("mixed", "Price কমাও, না হলে negative review এ page ভরিয়ে দেব, এটা আমার warning।"),
    ("regional", "দাম না কমাইলে দেখাইয়া দিমু, রিভিউ দিয়া তোমার ব্যবসা শেষ কইরা দিমু।"),
    ("banglish", "taka ferot na dile ami tomake dekhe nibo, amar lok ache."),
    ("regional", "বেশি কথা কইয়েন না, টেহা দিয়া দেন, নাইলে খবর আছে।"),
    ("standard", "আমার অর্থ ফেরত না দিলে আমি এই পেজটি রিপোর্ট করে বন্ধ করে ছাড়ব।"),
    ("mixed", "Product ta ঠিক ছিল but amake discount lagbe, na dile bad review dibo।"),
    ("banglish", "ei ta shesh bar bolchi, refund dao nahole page ta bondho kore dibo."),
    ("standard", "টাকা ফেরত না দিলে আমি সামাজিক মাধ্যমে আপনাদের মুখোশ খুলে দেব।"),
    ("regional", "আমারে ফেরত না দিলে তোমার পেজের নাম নষ্ট কইরা দিমু।"),
]

DELAY = [
    ("standard", "অর্ডার করেছি {d} দিন আগে, এখনো পার্সেল পৌঁছায়নি, কুরিয়ার কোনো সঠিক উত্তর দিচ্ছে না।"),
    ("banglish", "{d} din hoye gelo, parcel ekhono ashe nai, courier bole kal ashbe."),
    ("regional", "{d} দিন অইয়া গেল পার্সেল আইল না, কুরিয়ার খালি কয় কাইল আইব।"),
    ("mixed", "Parcel {d} din dhore transit e ache, কোনো update নেই, delivery late হচ্ছে।"),
    ("standard", "ঢাকার ভেতরে ডেলিভারি হওয়ার কথা ছিল ২ দিনে, অথচ {d} দিন পার হয়ে গেছে।"),
    ("banglish", "tracking e ek jayga tei atke ache onek din."),
    ("standard", "পার্সেলটি বহু দিন ধরে একই জায়গায় আটকে আছে, আমি আর অপেক্ষা করতে পারছি না।"),
    ("mixed", "Courier hub e stuck, প্রায় {d} দিন, আমার urgent ছিল।"),
    ("regional", "পার্সেল তো আইতেছেই না, {d} দিনের উপরে লাগাইয়া ফালাইছে।"),
    ("banglish", "eto deri hocche keno, delivery date ta to pera gelo."),
    ("regional", "কুরিয়ারে পার্সেল পইড়া আছে, নড়ে না, আমার কাম আটকাইয়া গেছে।"),
    ("standard", "বিলম্বের কারণে আমার প্রয়োজন মিটছে না, আমি পার্সেলের অবস্থান জানতে চাই।"),
    ("mixed", "Delivery date over হয়ে গেছে, tracking e কোনো movement নেই।"),
    ("banglish", "kobe ashbe amar parcel? din gune jachchi."),
    ("standard", "ট্র্যাকিংয়ে দেখাচ্ছে পার্সেল পথে আছে কিন্তু {d} দিনেও কোনো অগ্রগতি নেই।"),
    ("regional", "কুরিয়ার কিছু কইতে পারে না, পার্সেলের খবর নাই।"),
]

FAMILIES = {
    "NOT_RECEIVED": NOT_RECEIVED,
    "WRONG_ITEM": WRONG_ITEM,
    "DAMAGED": DAMAGED,
    "NOT_AS_DESCRIBED": NOT_AS_DESCRIBED,
    "WANT_REFUND": WANT_REFUND,
    "THREAT": THREAT,
    "DELAY": DELAY,
}
