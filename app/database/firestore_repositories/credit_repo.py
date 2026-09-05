from firebase_admin import firestore
from app.core.firebase import get_firestore_client

STARTER_CREDITS = 7

class CreditRepository:
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection("users")

    def get_credits(self, user_id: str) -> int:
        doc = self.collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("credits", STARTER_CREDITS)
        return STARTER_CREDITS

    def deduct_credits(self, user_id: str, amount: int = 1) -> bool:
        user_ref = self.collection.document(user_id)
        
        @firestore.transactional
        def update_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                # Initialize user with some credits if they don't exist yet
                transaction.set(ref, {"credits": STARTER_CREDITS - amount}, merge=True)
                return True
                
            current_credits = snapshot.to_dict().get("credits", STARTER_CREDITS)
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
                new_balance = STARTER_CREDITS + amount
                transaction.set(ref, {"credits": new_balance}, merge=True)
                return new_balance
                
            current_credits = snapshot.to_dict().get("credits", STARTER_CREDITS)
            new_balance = current_credits + amount
            transaction.update(ref, {"credits": new_balance})
            return new_balance
            
        transaction = self.db.transaction()
        return add_in_transaction(transaction, user_ref)

    def add_credits_idempotent(
        self, user_id: str, amount: int = 1, idempotency_key: str | None = None
    ) -> int:
        """Add credits at most once per (user, idempotency_key) logical event.

        Bug 4 (isBugCondition4, credits/add half): duplicate deliveries of the
        SAME logical credits/add event (client resends the same idempotency_key)
        must apply the amount AT MOST ONCE. The applied key is persisted in
        Firestore (durable across Render cold starts — no in-memory-only state,
        no Redis/queues), and the check-and-apply happens inside a single
        transaction so concurrent duplicate deliveries cannot double-apply.

        When ``idempotency_key`` is falsy, this degrades to the non-idempotent
        ``add_credits`` (preservation: legacy callers with no key behave as
        before). Distinct keys each apply once (Requirement 3.11).
        """
        if not idempotency_key:
            return self.add_credits(user_id, amount)

        user_ref = self.collection.document(user_id)
        # Scope the applied-key record per user so keys cannot collide/leak
        # across accounts. Stored as a subcollection document under the user.
        key_ref = user_ref.collection("credit_idempotency_keys").document(idempotency_key)

        @firestore.transactional
        def apply_in_transaction(transaction, uref, kref):
            # All reads must precede writes within a Firestore transaction.
            key_snapshot = kref.get(transaction=transaction)
            user_snapshot = uref.get(transaction=transaction)

            if not user_snapshot.exists:
                current_credits = STARTER_CREDITS
            else:
                current_credits = user_snapshot.to_dict().get("credits", STARTER_CREDITS)

            if key_snapshot.exists:
                # This logical event was already applied — return the CURRENT
                # balance WITHOUT re-applying (short-circuit duplicate delivery).
                return current_credits

            new_balance = current_credits + amount
            if not user_snapshot.exists:
                transaction.set(uref, {"credits": new_balance}, merge=True)
            else:
                transaction.update(uref, {"credits": new_balance})

            # Persist the applied key atomically with the balance change so the
            # apply and the record either both commit or neither does.
            transaction.set(
                kref,
                {
                    "amount": amount,
                    "applied_balance": new_balance,
                    "applied_at": firestore.SERVER_TIMESTAMP,
                },
            )
            return new_balance

        transaction = self.db.transaction()
        return apply_in_transaction(transaction, user_ref, key_ref)

credit_repo = CreditRepository()
