"""Small Mongo adapter for isolated runtime tests, not application persistence."""
from copy import deepcopy
from types import SimpleNamespace


def matches(doc, query):
    for key, value in query.items():
        actual = doc.get(key)
        if isinstance(value, dict):
            if "$in" in value and actual not in value["$in"]:
                return False
            if "$ne" in value and actual == value["$ne"]:
                return False
        elif actual != value:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    async def to_list(self, length=None):
        return self.docs[:length]

    def sort(self, key, direction):
        self.docs.sort(key=lambda d: str(d.get(key, "")), reverse=direction < 0)
        return self

    def skip(self, offset):
        self.docs = self.docs[offset:]
        return self

    def limit(self, limit):
        self.docs = self.docs[:limit]
        return self


class Collection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        if "_id" in doc and any(d.get("_id") == doc["_id"] for d in self.docs):
            raise ValueError("duplicate key")
        self.docs.append(deepcopy(doc))
        return SimpleNamespace(inserted_id=doc.get("_id"))

    async def insert_many(self, docs):
        for doc in docs:
            await self.insert_one(doc)

    async def find_one(self, query):
        return next((deepcopy(doc) for doc in self.docs if matches(doc, query)), None)

    def find(self, query, projection=None):
        return Cursor([doc for doc in self.docs if matches(doc, query)])

    async def update_one(self, query, update):
        for doc in self.docs:
            if matches(doc, query):
                doc.update(deepcopy(update.get("$set", {})))
                for key, value in update.get("$push", {}).items():
                    doc.setdefault(key, []).append(deepcopy(value))
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def update_many(self, query, update):
        for doc in self.docs:
            if matches(doc, query):
                doc.update(deepcopy(update.get("$set", {})))


class Database:
    def __init__(self):
        self.collections = {}

    def __getattr__(self, name):
        return self.collections.setdefault(name, Collection())


class Client:
    def __init__(self, db):
        self.db = db

    def get_default_database(self):
        return self.db

    def __getitem__(self, name):
        return self.db
