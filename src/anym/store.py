import secrets
from .classes import Message

class ConversationStore:
    def __init__(self) -> None:
        self.conversations: dict[str, list[Message]] = {} # TODO: replace with content of ./data/store.json file

    def create(self) -> str:
        token = secrets.token_urlsafe(16)
        self.conversations[token] = []
        return token

    def exists(self, token: str) -> bool:
        return token in self.conversations

    def history(self, token: str) -> list[Message]:
        return self.conversations[token]

    def add(self, token: str, msg: Message) -> None:
        self.conversations[token].append(msg)

store = ConversationStore()

# TODO: replace JSON file with actual database
def store_history(store):
    with open("./data/store.json", "w") as f:
        f.write(str(store.conversations))

print(secrets.token_urlsafe(64))
