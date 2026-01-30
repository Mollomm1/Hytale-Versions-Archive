import http.server
import socketserver
import json
import base64
import time
import uuid
import hashlib
import os
import struct
import re
import threading
import subprocess
import sys
from urllib.parse import urlparse, parse_qs

# --- Configuration ---
PORT = 4478
HOST = "localhost"
LAUNCHER_DIR = "launcher"
AVATAR_FILE = os.path.join(LAUNCHER_DIR, "avatar.json")
ACCOUNT_FILE = os.path.join(LAUNCHER_DIR, "account.json")

def load_username():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE, 'r') as f:
                return json.load(f).get("username", "Player")
        except: pass
    return "Player"

def save_username(username):
    with open(ACCOUNT_FILE, 'w') as f:
        json.dump({"username": username}, f)

current_username = load_username()
WEB_LOG_FILE = os.path.join(LAUNCHER_DIR, "web_server.log")
CLIENT_LOG_FILE = os.path.join(LAUNCHER_DIR, "hytale_client.log")
PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIL/aLunAFI+Ngi6tAYOftlbUvv/ZbAusYAQzUD2EsC6C
-----END PRIVATE KEY-----"""
KEY_ID = "ed25519-key-2024"
ISSUER = f"http://{HOST}:{PORT}"

# Ensure launcher directory exists
if not os.path.exists(LAUNCHER_DIR):
    os.makedirs(LAUNCHER_DIR)

# --- Minimal Ed25519 Implementation (Pure Python) ---
# Based on public domain implementations (Ref10)

def sha512(s):
    return hashlib.sha512(s).digest()

b = 256
q = 2**255 - 19
l = 2**252 + 27742317777372353535851937790883648493

def H(m):
    return hashlib.sha512(m).digest()

def expmod(b, e, m):
    if e == 0: return 1
    t = expmod(b, e // 2, m) ** 2 % m
    if e & 1: t = (t * b) % m
    return t

def inv(x):
    return expmod(x, q - 2, q)

d = -121665 * inv(121666)
I = expmod(2, (q - 1) // 4, q)

def xrecover(y):
    xx = (y*y - 1) * inv(d*y*y + 1)
    x = expmod(xx, (q + 3) // 8, q)
    if (x*x - xx) % q != 0: x = (x*I) % q
    if x % 2 != 0: x = q - x
    return x

By = 4 * inv(5)
Bx = xrecover(By)
B = [Bx % q, By % q]

def edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1*y2 + x2*y1) * inv(1 + d*x1*x2*y1*y2)
    y3 = (y1*y2 + x1*x2) * inv(1 - d*x1*x2*y1*y2)
    return [x3 % q, y3 % q]

def scalarmult(P, e):
    if e == 0: return [0, 1]
    Q = scalarmult(P, e // 2)
    Q = edwards(Q, Q)
    if e & 1: Q = edwards(Q, P)
    return Q

def encodeint(y):
    bits = [(y >> i) & 1 for i in range(b)]
    return b''.join([bytes([sum([bits[i * 8 + j] << j for j in range(8)])]) for i in range(b // 8)])

def encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
    return b''.join([bytes([sum([bits[i * 8 + j] << j for j in range(8)])]) for i in range(b // 8)])

def bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1

def publickey(sk):
    h = H(sk)
    a = 2**(b-2) + sum(2**i * bit(h, i) for i in range(3, b-2))
    A = scalarmult(B, a)
    return encodepoint(A)

def signature(m, sk, pk):
    h = H(sk)
    a = 2**(b-2) + sum(2**i * bit(h, i) for i in range(3, b-2))
    r = H(bytes([h[i] for i in range(b//8, b//4)]) + m)
    R = scalarmult(B, sum(2**i * bit(r, i) for i in range(2*b)))
    S = (sum(2**i * bit(r, i) for i in range(2*b)) + sum(2**i * bit(H(encodepoint(R) + pk + m), i) for i in range(2*b)) * a) % l
    return encodepoint(R) + encodeint(S)

# --- Crypto Helpers ---

def get_keys():
    # Parse PEM manually
    lines = PRIVATE_KEY_PEM.strip().splitlines()
    b64_data = "".join(lines[1:-1])
    data = base64.b64decode(b64_data)
    # The last 32 bytes of the ASN.1 structure is the seed
    seed = data[-32:]
    pk = publickey(seed)
    return seed, pk

SK_SEED, PUBLIC_KEY_BYTES = get_keys()
PUBLIC_KEY_B64 = base64.urlsafe_b64encode(PUBLIC_KEY_BYTES).decode('utf-8').rstrip('=')

def sign_jwt(payload):
    header = {"kid": KEY_ID, "typ": "JWT", "alg": "EdDSA"}
    
    header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    header_b64 = base64.urlsafe_b64encode(header_json).decode('utf-8').rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    sig = signature(signing_input, SK_SEED, PUBLIC_KEY_BYTES)
    sig_b64 = base64.urlsafe_b64encode(sig).decode('utf-8').rstrip('=')
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

# --- Data Management ---

CAPE_DEFINITIONS = {
    "game.base": [
        "Cape_Forest_Guardian"
    ],
    "game.deluxe": [
        "Cape_Bannerlord",
        "Cape_Featherbound",
        "Cape_Forest_Guardian",
        "Cape_King",
        "Cape_Knight",
        "Cape_Scavenger"
    ],
    "game.founder": [
        "Cape_Bannerlord",
        "Cape_Blazen_Wizard",
        "Cape_Featherbound",
        "Cape_Forest_Guardian",
        "Cape_King",
        "Cape_Knight",
        "Cape_New_Beginning",
        "Cape_PopStar",
        "Cape_Royal_Emissary",
        "Cape_Scavenger",
        "Cape_Seasons",
        "Cape_Void_Hero",
        "Cape_Wasteland_Marauder",
        "FrostwardenSet_Cape",
        "Hope_Of_Gaia_Cape"
    ]
}

COSMETIC_DEFINITIONS = {
    "bodyCharacteristic": [
        "Default",
        "Muscular"
    ],
    "earAccessory": [
        "AcornEarrings",
        "DoubleEarrings",
        "EarHoops",
        "SilverHoopsBead",
        "SimpleEarring",
        "SpiralEarring"
    ],
    "ears": [
        "Default",
        "Elf_Ears",
        "Elf_Ears_Large",
        "Elf_Ears_Large_Down",
        "Elf_Ears_Small",
        "Ogre_Ears"
    ],
    "eyebrows": [
        "Angry",
        "Bushy",
        "BushyThin",
        "Heavy",
        "Large",
        "Medium",
        "Plucked",
        "RoundThin",
        "Serious",
        "Shaved",
        "SmallRound",
        "Square",
        "Thick",
        "Thin"
    ],
    "eyes": [
        "Almond_Eyes",
        "Cat_Eyes",
        "Demonic_Eyes",
        "Goat_Eyes",
        "Large_Eyes",
        "Medium_Eyes",
        "Plain_Eyes",
        "Reptile_Eyes",
        "Square_Eyes"
    ],
    "faceAccessory": [
        "AgentGlasses",
        "AviatorGlasses",
        "BandageBlindfold",
        "BanditMask",
        "Blindfold",
        "BusinessGlasses",
        "ColouredGlasses",
        "CrazyGlasses",
        "EyePatch",
        "Glasses",
        "GlassesTiny",
        "Glasses_Monocle",
        "Goggles_Wasteland_Marauder",
        "HeartGlasses",
        "LargeGlasses",
        "MedicalEyePatch",
        "MouthCover",
        "MouthWheat",
        "Plaster",
        "RoundGlasses",
        "SunGlasses"
    ],
    "face": [
        "Face_Aged",
        "Face_Almond_Eyes",
        "Face_MakeUp",
        "Face_MakeUp_6",
        "Face_MakeUp_Freckles",
        "Face_MakeUp_Highlight",
        "Face_MakeUp_Older",
        "Face_MakeUp_Older2",
        "Face_Make_Up_2",
        "Face_Neutral",
        "Face_Neutral_Freckles",
        "Face_Older2",
        "Face_Scar",
        "Face_Stubble",
        "Face_Sunken",
        "Face_Tired_Eyes"
    ],
    "facialHair": [
        "Beard_Large",
        "Chin_Curtain",
        "CurlyLongBeard",
        "DoubleBraid",
        "Goatee",
        "GoateeLong",
        "Groomed",
        "Groomed_Large",
        "Handlebar",
        "Hip",
        "Medium",
        "Moustache",
        "PirateBeard",
        "PirateGoatee",
        "Short_Trimmed",
        "Soldier",
        "SoulPatch",
        "Stylish",
        "ThinGoatee",
        "Trimmed",
        "TripleBraid",
        "TwirlyMoustache",
        "VikingBeard",
        "WavyLongBeard"
    ],
    "gloves": [
        "Arctic_Scout_Gloves",
        "BasicGloves_Basic",
        "Battleworn_Gloves",
        "BoxingGloves",
        "Bracer_Daisy",
        "CatacombCrawler_Gloves",
        "FlowerBracer",
        "Gloves_Blazen_Wizard",
        "Gloves_Medium_Featherbound",
        "Gloves_Void_Hero",
        "Gloves_Wasteland_Marauder",
        "GoldenBracelets",
        "Hope_Of_Gaia_Gloves",
        "LeatherMittens",
        "LongGloves_Popstar",
        "LongGloves_Savanna",
        "Merchant_Gloves",
        "MiningGloves",
        "Scavenger_Gloves",
        "Shackles_Feran",
        "Straps_Leather"
    ],
    "haircut": [
        "AfroPuffs",
        "Balding",
        "Bangs",
        "BangsShavedBack",
        "BantuKnot",
        "Berserker",
        "Black",
        "Blond",
        "BlondCaramel",
        "BlondPlatinum",
        "BlondSand",
        "Blue",
        "BlueLight",
        "BobCut",
        "BowHair",
        "BowlCut",
        "Braid",
        "BraidDouble",
        "BraidedPonytail",
        "Brown",
        "BrownDark",
        "BrownLight",
        "Bubblegum",
        "Bun",
        "BuzzCut",
        "Cat",
        "CentrePart",
        "ChopsticksPonyTail",
        "Copper",
        "Cornrows",
        "Cowlick",
        "Curly",
        "CurlyShort",
        "CuteEmoBangs",
        "CutePart",
        "DoublePart",
        "Dreadlocks",
        "ElfBackBun",
        "Emo",
        "EmoBangs",
        "EmoWavy",
        "FeatheredHair",
        "FighterBuns",
        "Fringe",
        "FrizzyLong",
        "FrizzyVolume",
        "FrontFlick",
        "FrontTied",
        "GenericLong",
        "GenericMedium",
        "GenericPuffy",
        "GenericShort",
        "Greaser",
        "Green",
        "Grey",
        "GreyAsh",
        "Lazy",
        "Long",
        "LongBangs",
        "LongCurly",
        "LongHairPigtail",
        "LongPigtails",
        "LongTied",
        "MaleElf",
        "MediumCurly",
        "Messy",
        "MessyBobcut",
        "MessyMop",
        "MessyWavy",
        "MidSinglePart",
        "Mohawk",
        "Morning",
        "MorningLong",
        "Pigtails",
        "Pink",
        "PinkBerry",
        "PonyBuns",
        "PonyTail",
        "PuffyPonytail",
        "PuffyQuiff",
        "Purple",
        "Quiff",
        "QuiffLeft",
        "RaiderMohawk",
        "Red",
        "RedDark",
        "RoseBun",
        "Rustic",
        "Samurai",
        "Scavenger_Hair",
        "ShortDreads",
        "SideBuns",
        "SidePonytail",
        "Sideslick",
        "Simple",
        "SingleSidePigtail",
        "Slickback",
        "SmallPigtails",
        "SpikedUp",
        "StraightHairBun",
        "Stylish",
        "StylishQuiff",
        "StylishWindswept",
        "SuperShirt",
        "SuperSideSlick",
        "SuperSlickback",
        "ThickBraid",
        "Turquoise",
        "Undercut",
        "VikinManBun",
        "Viking",
        "VikingWarrior",
        "WavyBraids",
        "WavyLong",
        "WavyPonytail",
        "WavyShort",
        "White",
        "WidePonytail",
        "Windswept",
        "Wings",
        "Witch"
    ],
    "headAccessory": [
        "AcornHairclip",
        "AcornNecktie",
        "Arctic_Scout_Hat",
        "Bandana",
        "BandanaSkull",
        "BanjoHat",
        "Battleworn_Helm",
        "Beanie",
        "BulkyBeanie",
        "BunnyBeanie",
        "Bunny_Ears",
        "CatBeanie",
        "CowboyHat",
        "ElfHat",
        "ExplorerGoggles",
        "FloppyBeanie",
        "FlowerCrown",
        "ForeheadProtector",
        "Forest_Guardian_Hat",
        "FrogBeanie",
        "FrostwardenSet_Hat",
        "GiHeadband",
        "Goggles",
        "HairDaisy",
        "HairHibiscus",
        "HairPeony",
        "HairRose",
        "Hat_Popstar",
        "HeadDaliah",
        "Head_Bandage",
        "Head_Crown",
        "Head_Tiara",
        "Headband",
        "Headband_Void_Hero",
        "Headphones",
        "HeadphonesDadCap",
        "Hood_Blazen_Wizard",
        "Hoodie",
        "Hoodie_Feran",
        "Hoodie_Ornated",
        "Hope_Of_Gaia_Crown",
        "LeatherCap",
        "Logo_Cap",
        "Merchant_Beret",
        "PirateBandana",
        "Pirate_Captain_Hat",
        "Ribbon",
        "RusticBeanie",
        "SantaHat",
        "Savanna_Scout_Hat",
        "ShapedCap_Chill",
        "StrawHat",
        "StripedBeanie",
        "TopHat",
        "Viking_Helmet",
        "WitchHat",
        "WorkoutCap"
    ],
    "mouth": [
        "Mouth_Cute",
        "Mouth_Default",
        "Mouth_Long",
        "Mouth_Makeup",
        "Mouth_Orc",
        "Mouth_Thin",
        "Mouth_Tiny",
        "Mouth_Vampire"
    ],
    "overpants": [
        "KneePads",
        "LongSocks_BasicWrap",
        "LongSocks_Bow",
        "LongSocks_Plain",
        "LongSocks_School",
        "LongSocks_Striped",
        "LongSocks_Torn"
    ],
    "overtop": [
        "Adventurer_Dress",
        "AlpineExplorerJumper",
        "Arctic_Scout_Jacket",
        "Arm_Bandage",
        "AviatorJacket",
        "Bannerlord_Tunic",
        "Battleworn_Tunic",
        "BulkyShirtLong",
        "BulkyShirtLong_LeatherJacket",
        "BulkyShirt_FancyWaistcoat",
        "BulkyShirt_RoyalRobe",
        "BulkyShirt_RuralPattern",
        "BulkyShirt_RuralShirt",
        "BulkyShirt_Scarf",
        "BulkyShirt_StomachWrap",
        "BunnyHoody",
        "Chest_PuffyJersey",
        "Cheststrap",
        "Coat",
        "Collared_Cool",
        "DaisyTop",
        "DoubleButtonJacket",
        "ElfJacket",
        "Fancy_Coat",
        "Fantasy",
        "FantasyShawl",
        "FarmerVest",
        "Farmer_Dress",
        "Featherbound_Tunic",
        "FloppyBunnyJersey",
        "FlowyHalf",
        "ForestVest",
        "Forest_Guardian_Poncho",
        "FurLinedJacket",
        "GiShirt",
        "Golden_Bangles",
        "GoldtrimJacket",
        "HeartNecklace",
        "HeroShirt",
        "Hope_Of_GaiaOvertop",
        "Jacket",
        "JacketLong",
        "JacketShort",
        "Jacket_Popstar",
        "Jacket_Void_Hero",
        "Jacket_Voyager",
        "Jinbaori",
        "Jinbaori_Flower",
        "Jinbaori_Wave",
        "KhakiShirt",
        "LeatherVest",
        "LetterJacket",
        "LongBeltedJacket",
        "LongCardigan",
        "LooseSweater",
        "Merchant_Tunic",
        "MessyShirt",
        "MiniLeather",
        "NeckHigh_LeatherClad",
        "NeckHigh_Savanna",
        "Noble_Beige",
        "Oasis_Dress",
        "OnePiece_ApronDress",
        "OnePiece_SchoolDress",
        "OpenShirtBand",
        "PinstripeJacket",
        "Pirate",
        "PlainHoodie",
        "PlainJersey",
        "Polarneck",
        "Pookah_Necklace",
        "PuffyBomber",
        "PuffyJacket",
        "QuiltedTop",
        "RaggedVest",
        "RobeOvertops",
        "Robe_Blazen_Wizard",
        "Ronin",
        "RoughFabricBand",
        "SantaJacket",
        "Scarf",
        "Scarf_Large",
        "Scarf_Large_Stripped",
        "Scavenger_Poncho",
        "Shark_Tooth_Necklace",
        "ShortTartan",
        "SimpleDress",
        "SleevedDress",
        "SleevedDresswJersey",
        "StitchedShirt",
        "Straps_Wasteland_Marauder",
        "StylishJacket",
        "Suit_Jacket",
        "Tartan",
        "ThreadedOvertops",
        "TracksuitJacket",
        "TrenchCoat",
        "Tunic_Long",
        "Tunic_Villager",
        "Tunic_Weathered",
        "VikingVest",
        "Voidbearer_Top",
        "Winter_Jacket",
        "Wool_Jersey"
    ],
    "pants": [
        "ApprenticePants",
        "BannerlordQuilted",
        "Bermuda_Rolled",
        "BulkySuede",
        "CatacombCrawler_Shorts",
        "Colored_Trousers",
        "ColouredKhaki",
        "CostumePants",
        "Crinkled_Skirt",
        "DaisySkirt",
        "DenimSkirt",
        "DesertDress",
        "Dungarees",
        "ExplorerShorts",
        "Explorer_Trousers",
        "Forest_Bermuda",
        "Forest_Guardian",
        "Frilly_Skirt",
        "FrostwardenSet_Skirt",
        "GiPants",
        "GoldtrimSkirt",
        "HighSkirt_Popstar",
        "Hope_Of_Gaia_Skirt",
        "Icecream_Skirt",
        "Jeans",
        "JeansStrapped",
        "KhakiShorts",
        "LeatherPants",
        "Leggings",
        "LongDungarees",
        "Long_Dress",
        "Merchant_Pants",
        "Pants_Arctic_Scout",
        "Pants_Slim",
        "Pants_Slim_Faded",
        "Pants_Slim_Tracksuit",
        "Pants_Straight_WreckedJeans",
        "Pants_Void_Hero",
        "Pants_Wasteland_Marauder",
        "PinstripeTrousers",
        "Scavenger_Pants",
        "Short_Ample",
        "ShortyRolled",
        "Shorty_Mossy",
        "Shorty_Rotten",
        "SimpleSkirt",
        "SkaterShorts_Chunky",
        "Skirt",
        "Skirt_Savanna",
        "Slim_Short",
        "StripedPants",
        "StylishShorts",
        "SurvivorPants",
        "Villager_Bermuda",
        "Voidbearer_Pants"
    ],
    "shoes": [
        "AdventurerBoots",
        "Arctic",
        "Arctic_Scout_Boots",
        "BannerlordBoots",
        "BasicBoots",
        "BasicSandals",
        "BasicShoes",
        "BasicShoes_Buckle",
        "BasicShoes_Sandals",
        "BasicShoes_Shiny",
        "BasicShoes_Strap",
        "Battleworn_Boots",
        "Boots_Blazen_Wizard",
        "Boots_Long",
        "Boots_Thick",
        "Boots_Void_Hero",
        "Boots_Voyager",
        "CatacombCrawler_Boots",
        "DaisyShoes",
        "DesertBoots",
        "ElfBoots",
        "FashionableBoots",
        "Forest_Guardian_Boots",
        "FrostwardenSet_Boots",
        "Gem_Shoes",
        "GoldenBangle",
        "HeavyLeather",
        "HeeledBoots_Popstar",
        "HeeledBoots_Savanna",
        "HiBoots",
        "Hope_Of_Gaia_Boots",
        "Icecream_Shoes",
        "LeatherBoots",
        "Merchant_Boots",
        "MinerBoots",
        "SantaBoots",
        "Scavenger_HeeledBoots",
        "ScavenverLeatherBoots",
        "Shoes_Ornated",
        "SlipOns",
        "Slipons_CoolGaia",
        "Sneakers_Sneakers",
        "Sneakers_Wasteland_Marauder",
        "SnowBoots",
        "ThickSandals",
        "Trainers",
        "Voidbearer_Boots",
        "Wellies"
    ],
    "skinFeature": [],
    "undertop": [
        "Amazon_Top",
        "Bannerlord_Chainmail",
        "Belt_Shirt",
        "CatacombCrawler_Undertop",
        "ColouredSleeves",
        "ColouredStripes",
        "CostumeShirt",
        "Crinkled_Top",
        "DipCut",
        "DoubleShirt",
        "FarmerTop",
        "FlowerShirt",
        "Flowy_Shirt",
        "Forest_Guardian_LongShirt",
        "Frilly_Shirt",
        "FrostwardenSet_Top",
        "HeartCamisole",
        "LongSleevePeasantTop",
        "LongSleeveShirt",
        "LongSleeveShirt_ButtonUp",
        "LongSleeveShirt_GoldTrim",
        "Mercenary_Top",
        "PaintSpillShirt",
        "PastelFade",
        "PastelTracksuit",
        "RibbedLongShirt",
        "School_Blazer_Shirt",
        "School_Ribbon_Shirt",
        "School_Shirt",
        "Short_Sleeves_Shirt",
        "SmartShirt",
        "SpaghettiStrap",
        "StripedLong",
        "Stylish_Belt_Shirt",
        "SurvivorShirtBoy",
        "TieShirt",
        "Top_Wasteland_Marauder",
        "Tshirt_Logo",
        "Undertops_Tubetop",
        "VNeck_Shirt",
        "VikingShirt",
        "Voidbearer_CursedArm",
        "Wide_Neck_Shirt"
    ],
    "underwear": [
        "Bandeau",
        "Boxer",
        "Bra",
        "Suit"
    ]
}

DEFAULT_SKIN = {
    "bodyCharacteristic": "Muscular.11",
    "underwear": "Suit.Blue",
    "face": "Face_MakeUp_Highlight",
    "ears": "Default",
    "mouth": "Mouth_Default",
    "haircut": "SuperSlickback.BrownLight",
    "eyebrows": "SmallRound.BrownLight",
    "eyes": "Plain_Eyes.Black",
    "pants": "Colored_Trousers.Black",
    "undertop": "Stylish_Belt_Shirt.Black",
    "overtop": "DoubleButtonJacket.Black",
    "shoes": "FashionableBoots.Black",
    "headAccessory": "StrawHat.White"
}

def get_skin():
    if not os.path.exists(AVATAR_FILE):
        save_skin(DEFAULT_SKIN)
        return DEFAULT_SKIN
    try:
        with open(AVATAR_FILE, 'r') as f:
            return json.load(f)
    except:
        return DEFAULT_SKIN

def save_skin(data):
    with open(AVATAR_FILE, 'w') as f:
        json.dump(data, f)

def generate_uuid(username):
    # Deterministic UUID from username
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, username.lower()))

def generate_game_tokens(username, user_uuid, audience="hytale-client", scopes=None, scope="hytale:client"):
    if scopes is None: scopes = ["game.session"]
    
    # Set iat to 0 and exp to Jan 1st 2030
    iat = 0
    exp = 1893456000
    
    session_token = sign_jwt({
        "sub": user_uuid,
        "username": username,
        "iss": ISSUER,
        "iat": iat,
        "exp": exp,
        "scope": scope,
        "ver": "2.0",
        "aud": audience,
        "scopes": scopes,
        "t_ver": 1
    })
    
    identity_token = sign_jwt({
        "exp": exp,
        "iat": iat,
        "iss": ISSUER,
        "jti": str(uuid.uuid4()),
        "profile": {
            "username": username,
            "entitlements": ["game.base", "game.deluxe", "game.founder"],
            "skin": json.dumps(get_skin())
        },
        "scope": scope,
        "sub": user_uuid,
        "t_ver": 1
    })
    return session_token, identity_token, exp

# --- Global State ---
GRANT_STORE = {}

# --- Request Handler ---

class HytaleHandler(http.server.BaseHTTPRequestHandler):
    
    def _set_headers(self, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-type", content_type)
        self.end_headers()
        
    def get_user_from_token(self):
        auth = self.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            try:
                payload = json.loads(base64.urlsafe_b64decode(auth.split(" ")[1].split(".")[1] + "==").decode())
                username = payload.get("username")
                user_uuid = payload.get("sub")
                if username and user_uuid:
                    return username, user_uuid
            except: 
                pass
        return None, None

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        path = self.path.split('?')[0]

        if path == "/launcher/login":
            self.handle_login(data)
        elif path == "/server-join/auth-grant":
            self.handle_auth_grant(data)
        elif path == "/server-join/auth-token":
            self.handle_auth_token(data)
        elif path == "/game-session/refresh":
            self.handle_session_refresh(data)
        elif path == "/game-session/child":
            self.handle_child_session(data)
        elif path == "/game-session/new":
            self.handle_new_game_session(data)
        elif path == "/game-session/publicserver":
            self.handle_public_server(data)
        elif path == "/telemetry/client" or path == "/api/2/envelope":
            self._set_headers(201)
        elif path == "/launcher/register":
             # Fake register
             self._set_headers(200)
             self.wfile.write(json.dumps({"success": True, "message": "Registered", "user_uuid": str(uuid.uuid4())}).encode())
        else:
            self.send_error(404)

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        path = self.path.split('?')[0]

        if path == "/my-account/skin":
             try:
                 skin_data = json.loads(body)
                 save_skin(skin_data)
                 self._set_headers(204)
             except Exception as e:
                 self.send_error(400, str(e))
        else:
             self.send_error(404)

    def do_GET(self):
        path = self.path.split('?')[0]
        
        if path == "/launcher/info":
            self._set_headers()
            self.wfile.write(json.dumps({
                "name": "Hytale-Standalone",
                "version": "1.0.0",
                "description": "Standalone Local Launcher",
                "registration_mode": "OPEN"
            }).encode())
        elif path == "/launcher/account":
            self.handle_account()
        elif path == "/launcher/newsession":
            self.handle_newsession()
        elif path == "/.well-known/jwks.json":
            self._set_headers()
            self.wfile.write(json.dumps({
                "keys": [{
                    "kty": "OKP", "crv": "Ed25519", "x": PUBLIC_KEY_B64,
                    "kid": KEY_ID, "use": "sig", "alg": "EdDSA"
                }]
            }).encode())
        elif path == "/my-account/game-profile":
            self.handle_game_profile()
        elif path == "/my-account/cosmetics":
            self.handle_cosmetics()
        else:
            self.send_error(404)

    # --- Handlers ---

    def handle_login(self, data):
        username = data.get("username", "Player")
        user_uuid = generate_uuid(username)
        
        # Set iat to 0 and exp to Jan 1st 2030
        iat = 0
        exp = 1893456000
        
        token = sign_jwt({
            "sub": user_uuid,
            "username": username,
            "iss": ISSUER,
            "iat": iat,
            "exp": exp,
            "scope": "launcher",
            "ver": "2.0",
            "aud": "launcher",
            "scopes": ["launcher"],
            "t_ver": 1
        })
        
        self._set_headers()
        self.wfile.write(json.dumps({
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 15552000,
            "user_uuid": user_uuid,
            "username": username
        }).encode())

    def handle_account(self):
        username, user_uuid = self.get_user_from_token()
        if not username:
             username = "Player"
             user_uuid = generate_uuid(username)

        self._set_headers()
        self.wfile.write(json.dumps({
            "uuid": user_uuid,
            "username": username,
            "is_admin": True,
            "is_active": True,
            "entitlements": ["game.base", "game.deluxe", "game.founder"]
        }).encode())

    def handle_newsession(self):
        username, user_uuid = self.get_user_from_token()
        if not username:
             username = "Player"
             user_uuid = generate_uuid(username)

        session_token, identity_token, exp = generate_game_tokens(username, user_uuid)
        
        self._set_headers()
        self.wfile.write(json.dumps({
            "session_token": session_token,
            "identity_token": identity_token,
            "expires_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))
        }).encode())

    def handle_auth_grant(self, data):
        id_token = data.get("identityToken")
        aud = data.get("aud")
        
        try:
             payload = json.loads(base64.urlsafe_b64decode(id_token.split(".")[1] + "==").decode())
             user_uuid = payload.get("sub")
             username = payload.get("profile", {}).get("username", "Player")
        except:
             self.send_error(400, "Invalid token")
             return

        grant = "".join([uuid.uuid4().hex for _ in range(3)]) 
        GRANT_STORE[grant] = {"aud": aud, "uuid": user_uuid, "username": username}
        
        self._set_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "authorizationGrant": grant,
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 300))
        }).encode())

    def handle_auth_token(self, data):
        global current_username
        grant = data.get("authorizationGrant")
        fingerprint = data.get("x509Fingerprint")
            
        user_uuid = generate_uuid(current_username)
        audience = "xxxxxxx"
        username = current_username
        
        # Set iat to 0 and exp to Jan 1st 2030
        iat = 0
        exp = 1893456000
        
        acc_token = sign_jwt({
            "aud": audience,
            "cnf": {"x5t#S256": fingerprint},
            "exp": exp,
            "iat": iat,
            "ip": "127.0.0.1",
            "iss": ISSUER,
            "sub": user_uuid,
            "username": username
        })
        
        id_token = sign_jwt({
            "exp": exp,
            "iat": iat,
            "iss": ISSUER,
            "jti": str(uuid.uuid4()),
            "profile": {
                "username": username,
                "entitlements": ["game.base"],
                "skin": json.dumps(get_skin())
            },
            "scope": "hytale:server",
            "sub": user_uuid,
            "t_ver": 1
        })
        
        sess_token = sign_jwt({
             "sub": user_uuid,
             "username": username,
             "iss": ISSUER,
             "iat": iat,
             "exp": exp,
             "scope": "hytale:client",
             "aud": audience,
             "scopes": ["game.play", "server.join"],
             "t_ver": 1
        })

        self._set_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "accessToken": acc_token,
            "identityToken": id_token,
            "sessionToken": sess_token,
            "scopes": ["game.play", "server.join"],
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))
        }).encode())

    def handle_game_profile(self):
        username, user_uuid = self.get_user_from_token()
        if not username:
             username = "Player"
             user_uuid = generate_uuid(username)
             
        self._set_headers()
        self.wfile.write(json.dumps({
            "createdAt": "2025-01-01T12:00:00Z",
            "entitlements": ["game.base", "game.deluxe", "game.founder"],
            "skin": json.dumps(get_skin()),
            "username": username,
            "uuid": user_uuid,
        }).encode())

    def handle_cosmetics(self):
        allowed_capes = []
        for pack in CAPE_DEFINITIONS.values():
            allowed_capes.extend(pack)
        allowed_capes = list(set(allowed_capes))
        response = {"cape": allowed_capes, **COSMETIC_DEFINITIONS}
        self._set_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_session_refresh(self, data):
        username, user_uuid = self.get_user_from_token()
        if not username:
             username = "Player"
             user_uuid = generate_uuid(username)

        session_token, identity_token, exp = generate_game_tokens(username, user_uuid, audience="refreshed-session")

        self._set_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "identityToken": identity_token,
            "sessionToken": session_token,
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp)),
            "refreshedAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time()))
        }).encode())
        
    def handle_child_session(self, data):
        username, user_uuid = self.get_user_from_token()
        if not username:
             self.send_error(401, "Unauthorized")
             return

        scopes = data.get("scopes", ["hytale:server"])
        target_scope = "hytale:server"
        if "hytale:editor" in scopes:
            target_scope = "hytale:editor"
        elif "hytale:server" in scopes:
            target_scope = "hytale:server"
            
        session_id = uuid.uuid4().hex
        
        # Use existing helper but with overridden scope/audience
        session_token, identity_token, exp = generate_game_tokens(
            username, 
            user_uuid, 
            audience=session_id, 
            scope=target_scope, 
            scopes=["game.child"]
        )

        self._set_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "sessionId": session_id,
            "sessionToken": session_token,
            "identityToken": identity_token,
            "parentId": user_uuid,
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))
        }).encode())

    def handle_public_server(self, data):
        # Emulate server user
        username = "SERVER"
        user_uuid = generate_uuid(username)
        
        session_token, identity_token, exp = generate_game_tokens(username, user_uuid, audience="hytale-server", scope="hytale:server")
        
        self._set_headers()
        self.wfile.write(json.dumps({
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp)),
            "identityToken": identity_token,
            "sessionToken": session_token,
        }).encode())

    def handle_new_game_session(self, data):
        # We need the user from UUID. Since we don't have a DB, and UUIDs are deterministic...
        # We can't reverse UUID -> Username.
        # But we can try to trust the client if it sends something, or default to Player?
        # Actually, new game session is usually for resetting sessions.
        # We'll just assume the request is for the "current" user context if we can guess it, 
        # or we just assume "Player" if the UUID matches "Player"'s UUID.
        
        # For a proper standalone fix: we check if UUID matches "SERVER" (special case) or generic logic.
        req_uuid = data.get("uuid")
        
        # NOTE: In this standalone script without a DB, we can't reliably get username from UUID 
        # unless it matches our current "Player" or "SERVER".
        # We'll default to "Player" for now if it's not SERVER.
        
        username = "Player"
        if req_uuid == generate_uuid("SERVER"):
            username = "SERVER"
        
        # If the requester knew the UUID, they probably know the username.
        # But we only have the UUID here.
        
        session_token, identity_token, exp = generate_game_tokens(username, req_uuid, audience="refreshed-session")
        
        self._set_headers()
        self.wfile.write(json.dumps({
            "expiresAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp)),
            "identityToken": identity_token,
            "sessionToken": session_token,
        }).encode())

    def log_message(self, format, *args):
        # Override to write to file
        try:
            with open(WEB_LOG_FILE, "a") as f:
                f.write("%s - - [%s] %s\n" %
                        (self.client_address[0],
                         self.log_date_time_string(),
                         format%args))
        except:
            pass # Fallback or ignore

# Global server instance for shutdown
httpd_server = None

def run_server():
    global httpd_server
    # Clear log on start
    with open(WEB_LOG_FILE, "w") as f:
        f.write(f"Starting Standalone Hytale Auth Server on {HOST}:{PORT}\n")
        
    print(f"Starting Standalone Hytale Auth Server on {HOST}:{PORT}")
    
    # Prevent 'Address already in use' errors
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer((HOST, PORT), HytaleHandler) as httpd:
        httpd_server = httpd
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()

def main():
    global current_username
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    time.sleep(1) # Wait for server to start
    
    try:
        while True:
            print("\n=== Hytale Standalone Launcher ===")
            print(f"Current Username: {current_username}")
            print(f"User UUID: {generate_uuid(current_username)}")
            print("1. Set Username")
            print("2. Launch Game")
            print("3. Exit")
            
            try:
                choice = input("Enter choice: ").strip()
            except EOFError:
                break
            
            if choice == "1":
                new_name = input("Enter new username: ").strip()
                if new_name:
                    current_username = new_name
                    save_username(current_username)
            elif choice == "2":
                uuid_str = generate_uuid(current_username)
                sess_tok, id_tok, _ = generate_game_tokens(current_username, uuid_str)
                
                # Paths relative to current directory
                cwd = os.getcwd()
                is_windows = os.name == 'nt'

                if is_windows:
                    game_exec = os.path.join(cwd, "game", "data", "Client", "HytaleClient.exe")
                    java_exec = os.path.join(cwd, "game", "jre", "bin", "java.exe")
                else:
                    game_exec = os.path.join(cwd, "game", "data", "Client", "HytaleClient")
                    java_exec = os.path.join(cwd, "game", "jre", "bin", "java")

                app_dir = os.path.join(cwd, "game", "data")
                user_dir = os.path.join(cwd, "UserData")
                
                if not os.path.exists(user_dir):
                    os.makedirs(user_dir)
                
                # Check if files exist (optional but good for debugging)
                if not os.path.exists(game_exec):
                     print(f"WARNING: Game executable not found at {game_exec}")
                if not os.path.exists(java_exec):
                     print(f"WARNING: Java executable not found at {java_exec}")
                
                # Make executable if needed (Linux only)
                if not is_windows:
                    if os.path.exists(game_exec):
                        os.chmod(game_exec, 0o755)
                    if os.path.exists(java_exec):
                        os.chmod(java_exec, 0o755)

                cmd = [
                    game_exec,
                    "--app-dir", app_dir,
                    "--user-dir", user_dir,
                    "--java-exec", java_exec,
                    "--auth-mode", "authenticated",
                    "--uuid", uuid_str,
                    "--name", current_username,
                    "--identity-token", id_tok,
                    "--session-token", sess_tok
                ]
                
                print(f"Launching game (Logs -> {CLIENT_LOG_FILE})...")
                try:
                    # Open log file for the client
                    with open(CLIENT_LOG_FILE, "w") as log_file:
                         # Use Popen to redirect stdout/stderr
                         process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
                         process.wait() # Wait for game to exit
                except Exception as e:
                    print(f"Error launching game: {e}")
            elif choice == "3":
                break
            else:
                print("Invalid choice.")
    except KeyboardInterrupt:
        pass
    finally:
        print("\nExiting...")
        if httpd_server:
            print("Shutting down server...")
            httpd_server.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    main()