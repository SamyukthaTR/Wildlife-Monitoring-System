"""Label vocabularies for the three models, and how each maps onto taxonomy.

The honesty rule this module encodes: a model label is only treated as a species
identification when the label itself names a species. COCO's "bird" and
AudioSet's "Bird" both mean class Aves; ImageNet's "African elephant" means
Loxodonta africana. They are stored at different ranks accordingly.
"""

# ---------------------------------------------------------------------------
# YOLOv8 / COCO
# ---------------------------------------------------------------------------
# COCO has exactly ten animal classes. All are coarse: "zebra" is a genus
# (Equus, three species), "bear" is a whole family. Detection tells us an animal
# is present and where; naming it is the classifier's job.
COCO_ANIMAL_CLASSES = {
    "bird":     {"taxon": "Aves",        "group": "bird",   "rank": "class"},
    "cat":      {"taxon": "Felidae",     "group": "mammal", "rank": "family"},
    "dog":      {"taxon": "Canidae",     "group": "mammal", "rank": "family"},
    "horse":    {"taxon": "Equidae",     "group": "mammal", "rank": "family"},
    "sheep":    {"taxon": "Bovidae",     "group": "mammal", "rank": "family"},
    "cow":      {"taxon": "Bovidae",     "group": "mammal", "rank": "family"},
    "elephant": {"taxon": "Elephantidae", "group": "mammal", "rank": "family"},
    "bear":     {"taxon": "Ursidae",     "group": "mammal", "rank": "family"},
    "zebra":    {"taxon": "Equus",       "group": "mammal", "rank": "genus"},
    "giraffe":  {"taxon": "Giraffa",     "group": "mammal", "rank": "genus"},
}


# ---------------------------------------------------------------------------
# ResNet-50 / ImageNet-1k
# ---------------------------------------------------------------------------
# ImageNet-1k class indices 0-397 are animals, ordered taxonomically:
#   0-116   fish, amphibians, reptiles, birds (with birds at 7-24, 80-100)
#   118-396 invertebrates and mammals
# Index 398 onward is objects, plants, food and scenery.
#
# Rather than hardcode 398 names here, the ranges below classify an index into a
# species group; the human-readable label comes from the model's own metadata at
# runtime. The boundaries follow the standard ImageNet-1k ordering.
IMAGENET_ANIMAL_MAX_INDEX = 397

IMAGENET_GROUP_RANGES = [
    (0, 6, "marine"),         # tench, goldfish, sharks, rays
    (7, 24, "bird"),          # cock through black swan... (see 80-100 too)
    (25, 32, "amphibian"),    # salamanders, newts, frogs
    (33, 68, "reptile"),      # turtles, lizards, snakes
    (69, 79, "insect"),       # scorpion, spiders, ticks (arachnids grouped here)
    (80, 100, "bird"),        # grouse, peacock, quail, parrot, toucan, hornbill
    (101, 101, "mammal"),     # tusker
    (102, 106, "marine"),     # echidna/platypus adjacency, sea life
    (107, 121, "marine"),     # jellyfish, corals, sea slugs, molluscs
    (122, 130, "marine"),     # crabs, lobsters, crayfish
    (131, 146, "bird"),       # herons, storks, cranes, shorebirds
    (147, 157, "marine"),     # whales, dugong, sea lion
    (158, 268, "mammal"),     # dogs and wild canids
    (269, 275, "mammal"),     # wolves, foxes
    (276, 293, "mammal"),     # hyena, big cats
    (294, 297, "mammal"),     # bears
    (298, 319, "insect"),     # beetles, butterflies, dragonflies, bees, ants
    (320, 335, "insect"),
    (336, 397, "mammal"),     # rodents, ungulates, primates, marsupials
]

# ImageNet labels that name a domestic breed rather than a wild species. These
# still identify a real taxon, but calling a camera-trap animal "Egyptian cat"
# overstates the result, so they are recorded at coarse rank.
IMAGENET_DOMESTIC_HINTS = (
    "retriever", "terrier", "spaniel", "hound", "shepherd", "poodle", "collie",
    "setter", "pointer", "sheepdog", "mastiff", "bulldog", "pinscher", "corgi",
    "schnauzer", "dalmatian", "chihuahua", "pekinese", "pug", "malamute",
    "husky", "tabby", "egyptian cat", "persian cat", "siamese cat",
    "domestic", "ox", "oxcart",
)


def imagenet_group_for_index(index: int) -> str | None:
    """Species group for an ImageNet-1k class index, or None if not an animal."""
    if index > IMAGENET_ANIMAL_MAX_INDEX:
        return None
    for low, high, group in IMAGENET_GROUP_RANGES:
        if low <= index <= high:
            return group
    return "other"


def imagenet_is_domestic(label: str) -> bool:
    lowered = label.lower()
    return any(hint in lowered for hint in IMAGENET_DOMESTIC_HINTS)


# ---------------------------------------------------------------------------
# AST / AudioSet
# ---------------------------------------------------------------------------
# AudioSet's 527 classes include a biological branch and an environmental one.
# We keep both: biological labels become acoustic detections, environmental ones
# are stored with is_noise=True so the filtering is visible and auditable rather
# than silently dropping data.
#
# No AudioSet class names a species. Everything here is coarse by construction,
# which is why acoustic detections are excluded from species-level diversity
# indices.
AUDIOSET_BIOLOGICAL = {
    # birds
    "bird": ("Aves", "bird"),
    "bird vocalization, bird call, bird song": ("Aves", "bird"),
    "chirp, tweet": ("Aves", "bird"),
    "squawk": ("Aves", "bird"),
    "pigeon, dove": ("Columbidae", "bird"),
    "coo": ("Columbidae", "bird"),
    "crow": ("Corvus", "bird"),
    "caw": ("Corvus", "bird"),
    "owl": ("Strigiformes", "bird"),
    "hoot": ("Strigiformes", "bird"),
    "bird flight, flapping wings": ("Aves", "bird"),
    "duck": ("Anatidae", "bird"),
    "quack": ("Anatidae", "bird"),
    "goose": ("Anserinae", "bird"),
    "honk": ("Anserinae", "bird"),
    "turkey": ("Meleagris", "bird"),
    "gobble": ("Meleagris", "bird"),
    "chicken, rooster": ("Gallus", "bird"),
    "cluck": ("Gallus", "bird"),
    "crowing, cock-a-doodle-doo": ("Gallus", "bird"),
    "fowl": ("Galliformes", "bird"),
    "chirp tone": ("Aves", "bird"),
    "squeal": ("Animalia", "other"),
    # mammals
    "animal": ("Animalia", "other"),
    "wild animals": ("Animalia", "other"),
    "livestock, farm animals, working animals": ("Mammalia", "mammal"),
    "roaring cats (lions, tigers)": ("Pantherinae", "mammal"),
    "roar": ("Mammalia", "mammal"),
    "growling": ("Mammalia", "mammal"),
    "bark": ("Canidae", "mammal"),
    "howl": ("Canidae", "mammal"),
    "bow-wow": ("Canidae", "mammal"),
    "whimper (dog)": ("Canidae", "mammal"),
    "yip": ("Canidae", "mammal"),
    "dog": ("Canis", "mammal"),
    "cat": ("Felidae", "mammal"),
    "meow": ("Felidae", "mammal"),
    "purr": ("Felidae", "mammal"),
    "caterwaul": ("Felidae", "mammal"),
    "hiss": ("Animalia", "other"),
    "cattle, bovinae": ("Bovinae", "mammal"),
    "moo": ("Bovinae", "mammal"),
    "cowbell": ("Bovinae", "mammal"),
    "pig": ("Sus", "mammal"),
    "oink": ("Sus", "mammal"),
    "goat": ("Capra", "mammal"),
    "bleat": ("Bovidae", "mammal"),
    "sheep": ("Ovis", "mammal"),
    "horse": ("Equus", "mammal"),
    "neigh, whinny": ("Equus", "mammal"),
    "clip-clop": ("Equus", "mammal"),
    "rodents, rats, mice": ("Rodentia", "mammal"),
    "mouse": ("Rodentia", "mammal"),
    "squeak": ("Rodentia", "mammal"),
    "bat": ("Chiroptera", "mammal"),
    "whale vocalization": ("Cetacea", "marine"),
    # amphibians and insects
    "frog": ("Anura", "amphibian"),
    "croak": ("Anura", "amphibian"),
    "insect": ("Insecta", "insect"),
    "cricket": ("Gryllidae", "insect"),
    "mosquito": ("Culicidae", "insect"),
    "fly, housefly": ("Diptera", "insect"),
    "buzz": ("Insecta", "insect"),
    "bee, wasp, etc.": ("Hymenoptera", "insect"),
    "rattle": ("Animalia", "other"),
}

# Environmental and anthropogenic classes worth recording as filtered noise.
# Anything AudioSet returns that is in neither map is also treated as noise --
# this set exists to give the common cases a readable reason.
AUDIOSET_ENVIRONMENTAL = {
    "silence", "wind", "wind noise (microphone)", "rustling leaves",
    "rustle", "rain", "raindrop", "rain on surface", "thunder", "thunderstorm",
    "stream", "water", "waves, surf", "fire", "speech", "male speech, man speaking",
    "female speech, woman speaking", "conversation", "narration, monologue",
    "vehicle", "car", "engine", "motorcycle", "aircraft", "helicopter",
    "white noise", "pink noise", "static", "hum", "mains hum", "noise",
    "environmental noise", "inside, small room", "outside, rural or natural",
    "outside, urban or manmade", "music", "microphone",
}


def audioset_lookup(label: str):
    """Return (taxon, group) for a biological AudioSet label, else None."""
    return AUDIOSET_BIOLOGICAL.get(label.strip().lower())


def audioset_is_noise(label: str) -> bool:
    """True for anything that is not a biological sound.

    Unknown labels count as noise: the platform would rather under-report an
    acoustic detection than assert an animal that was never identified.
    """
    return audioset_lookup(label) is None
