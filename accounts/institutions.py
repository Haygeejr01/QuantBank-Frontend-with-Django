INSTITUTIONS = [
    {"code": "accessbank", "name": "Access Bank", "short_name": "Access", "bank_code": "044", "prefix": "01", "kind": "bank"},
    {"code": "gtbank", "name": "Guaranty Trust Bank", "short_name": "GTBank", "bank_code": "058", "prefix": "02", "kind": "bank"},
    {"code": "zenithbank", "name": "Zenith Bank", "short_name": "Zenith", "bank_code": "057", "prefix": "03", "kind": "bank"},
    {"code": "uba", "name": "United Bank for Africa", "short_name": "UBA", "bank_code": "033", "prefix": "04", "kind": "bank"},
    {"code": "firstbank", "name": "First Bank of Nigeria", "short_name": "FirstBank", "bank_code": "011", "prefix": "05", "kind": "bank"},
    {"code": "opay", "name": "OPay", "short_name": "OPay", "bank_code": "100004", "prefix": "06", "kind": "wallet"},
    {"code": "moniepoint", "name": "Moniepoint Microfinance Bank", "short_name": "Moniepoint", "bank_code": "50515", "prefix": "07", "kind": "wallet"},
    {"code": "kuda", "name": "Kuda Microfinance Bank", "short_name": "Kuda", "bank_code": "50211", "prefix": "08", "kind": "wallet"},
    {"code": "palmpay", "name": "PalmPay", "short_name": "PalmPay", "bank_code": "100033", "prefix": "09", "kind": "wallet"},
    {"code": "polarisbank", "name": "Polaris Bank", "short_name": "Polaris", "bank_code": "076", "prefix": "10", "kind": "bank"},
    {"code": "stanbicibtc", "name": "Stanbic IBTC Bank", "short_name": "Stanbic", "bank_code": "221", "prefix": "11", "kind": "bank"},
    {"code": "sterlingbank", "name": "Sterling Bank", "short_name": "Sterling", "bank_code": "232", "prefix": "12", "kind": "bank"},
    {"code": "fidelitybank", "name": "Fidelity Bank", "short_name": "Fidelity", "bank_code": "070", "prefix": "13", "kind": "bank"},
    {"code": "fcmb", "name": "First City Monument Bank", "short_name": "FCMB", "bank_code": "214", "prefix": "14", "kind": "bank"},
    {"code": "unionbank", "name": "Union Bank of Nigeria", "short_name": "Union Bank", "bank_code": "032", "prefix": "15", "kind": "bank"},
    {"code": "wema", "name": "Wema Bank", "short_name": "Wema", "bank_code": "035", "prefix": "16", "kind": "bank"},
    {"code": "alat", "name": "ALAT by Wema", "short_name": "ALAT", "bank_code": "035A", "prefix": "17", "kind": "wallet"},
    {"code": "providus", "name": "Providus Bank", "short_name": "Providus", "bank_code": "101", "prefix": "18", "kind": "bank"},
    {"code": "keystone", "name": "Keystone Bank", "short_name": "Keystone", "bank_code": "082", "prefix": "19", "kind": "bank"},
    {"code": "ecobank", "name": "Ecobank Nigeria", "short_name": "Ecobank", "bank_code": "050", "prefix": "20", "kind": "bank"},
    {"code": "standardchartered", "name": "Standard Chartered Bank", "short_name": "Standard Chartered", "bank_code": "068", "prefix": "21", "kind": "bank"},
    {"code": "unitybank", "name": "Unity Bank", "short_name": "Unity", "bank_code": "215", "prefix": "22", "kind": "bank"},
    {"code": "jaizbank", "name": "Jaiz Bank", "short_name": "Jaiz", "bank_code": "301", "prefix": "23", "kind": "bank"},
    {"code": "globusbank", "name": "Globus Bank", "short_name": "Globus", "bank_code": "103", "prefix": "24", "kind": "bank"},
    {"code": "titantrust", "name": "Titan Trust Bank", "short_name": "Titan Trust", "bank_code": "102", "prefix": "25", "kind": "bank"},
    {"code": "suntrust", "name": "SunTrust Bank", "short_name": "SunTrust", "bank_code": "100", "prefix": "26", "kind": "bank"},
    {"code": "tajbank", "name": "TAJBank", "short_name": "TAJBank", "bank_code": "302", "prefix": "27", "kind": "bank"},
    {"code": "premiumtrust", "name": "PremiumTrust Bank", "short_name": "PremiumTrust", "bank_code": "105", "prefix": "28", "kind": "bank"},
    {"code": "optimusbank", "name": "Optimus Bank", "short_name": "Optimus", "bank_code": "107", "prefix": "29", "kind": "bank"},
    {"code": "parallexbank", "name": "Parallex Bank", "short_name": "Parallex", "bank_code": "104", "prefix": "30", "kind": "bank"},
]

INSTITUTION_CHOICES = [(item["code"], item["name"]) for item in INSTITUTIONS]
INSTITUTION_BY_CODE = {item["code"]: item for item in INSTITUTIONS}


def institution_name(code):
    institution = INSTITUTION_BY_CODE.get(code)
    return institution["name"] if institution else code


def institution_prefix(code):
    institution = INSTITUTION_BY_CODE.get(code)
    return institution["prefix"] if institution else "99"
