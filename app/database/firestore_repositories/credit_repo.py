from firebase_admin import firestore
from app.core.firebase import get_firestore_client

class CreditRepository:
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection("users")

    def get_credits(self, user_id: str) -> int:
        doc = self.collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("credits", 10)
        return 10

    def deduct_credits(self, user_id: str, amount: int = 1) -> bool:
        user_ref = self.collection.document(user_id)
        
        @firestore.transactional
        def update_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                # Initialize user with some credits if they don't exist yet
                transaction.set(ref, {"credits": 10 - amount}, merge=True)
                return True
                
            current_credits = snapshot.to_dict().get("credits", 10)
            if current_credits >= amount:
                transaction.update(ref, {"credits": current_credits - amount})
                return True
            return False
            
        transaction = self.db.transaction()
        return update_in_transaction(transaction, user_ref)

    def add_credits(self, user_id: str, amount: int = 1) -> int:
        user_ref = self.collection.document(user_id)
        
        @firestore.transactional
        def add_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                new_balance = 10 + amount
                transaction.set(ref, {"credits": new_balance}, merge=True)
                return new_balance
                
            current_credits = snapshot.to_dict().get("credits", 10)
            new_balance = current_credits + amount
            transaction.update(ref, {"credits": new_balance})
            return new_balance
            
        transaction = self.db.transaction()
        return add_in_transaction(transaction, user_ref)

credit_repo = CreditRepository()
