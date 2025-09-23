from typing import Optional, Any, List, Dict
import pymongo
from pymongo.errors import ConnectionError
import uuid
from datetime import datetime
import logging
import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """
        Initialize MongoDB client and collections.
        Raises ConnectionError if MongoDB connection fails.
        """
        try:
            self.client = pymongo.MongoClient(config.mongodb_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client["chatgpt_telegram_bot"]
            self.user_collection = self.db["user"]
            self.dialog_collection = self.db["dialog"]
            # Create indexes for better query performance
            self._create_indexes()
        except ConnectionError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise ConnectionError("Could not connect to MongoDB database")

    def _create_indexes(self):
        """Create indexes for efficient queries."""
        self.user_collection.create_index([("_id", pymongo.ASCENDING)], unique=True)
        self.dialog_collection.create_index([("user_id", pymongo.ASCENDING), ("start_time", pymongo.DESCENDING)])
        self.dialog_collection.create_index([("_id", pymongo.ASCENDING)], unique=True)

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False) -> bool:
        """
        Check if a user exists in the database.
        Args:
            user_id: Telegram user ID
            raise_exception: If True, raise ValueError if user doesn't exist
        Returns:
            bool: True if user exists, False otherwise
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        if raise_exception:
            raise ValueError(f"User {user_id} does not exist")
        return False

    def add_new_user(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> None:
        """
        Add a new user to the database.
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            username: User's Telegram username
            first_name: User's first name
            last_name: User's last name
        """
        if not isinstance(user_id, int) or not isinstance(chat_id, int):
            raise ValueError("user_id and chat_id must be integers")
        if not self.check_if_user_exists(user_id):
            user_dict = {
                "_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_interaction": datetime.now(),
                "first_seen": datetime.now(),
                "current_dialog_id": None,
                "current_chat_mode": "assistant",
                "current_model": config.models["available_text_models"][0],
                "n_used_tokens": {},
                "n_generated_images": 0,
                "n_transcribed_seconds": 0.0
            }
            try:
                self.user_collection.insert_one(user_dict)
                logger.info(f"Added new user: {user_id}")
            except pymongo.errors.PyMongoError as e:
                logger.error(f"Failed to add new user {user_id}: {e}")
                raise

    def start_new_dialog(self, user_id: int) -> str:
        """
        Start a new dialog for the user.
        Args:
            user_id: Telegram user ID
        Returns:
            str: New dialog ID
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        dialog_id = str(uuid.uuid4())
        dialog_dict = {
            "_id": dialog_id,
            "user_id": user_id,
            "chat_mode": self.get_user_attribute(user_id, "current_chat_mode"),
            "start_time": datetime.now(),
            "model": self.get_user_attribute(user_id, "current_model"),
            "messages": []
        }
        try:
            self.dialog_collection.insert_one(dialog_dict)
            self.user_collection.update_one(
                {"_id": user_id},
                {"$set": {"current_dialog_id": dialog_id}}
            )
            logger.info(f"Started new dialog {dialog_id} for user {user_id}")
            return dialog_id
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Failed to start new dialog for user {user_id}: {e}")
            raise

    def get_user_attribute(self, user_id: int, key: str) -> Any:
        """
        Get a user attribute by key.
        Args:
            user_id: Telegram user ID
            key: Attribute key to retrieve
        Returns:
            Any: Attribute value or None if not found
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        user_dict = self.user_collection.find_one({"_id": user_id})
        return user_dict.get(key)

    def set_user_attribute(self, user_id: int, key: str, value: Any) -> None:
        """
        Set a user attribute.
        Args:
            user_id: Telegram user ID
            key: Attribute key
            value: Attribute value
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        try:
            self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})
            logger.debug(f"Set attribute {key} for user {user_id}")
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Failed to set attribute {key} for user {user_id}: {e}")
            raise

    def update_n_used_tokens(self, user_id: int, model: str, n_input_tokens: int, n_output_tokens: int) -> None:
        """
        Update the number of used tokens for a user and model.
        Args:
            user_id: Telegram user ID
            model: Model name
            n_input_tokens: Number of input tokens
            n_output_tokens: Number of output tokens
        """
        if not isinstance(n_input_tokens, int) or not isinstance(n_output_tokens, int):
            raise ValueError("n_input_tokens and n_output_tokens must be integers")
        n_used_tokens_dict = self.get_user_attribute(user_id, "n_used_tokens") or {}
        if model in n_used_tokens_dict:
            n_used_tokens_dict[model]["n_input_tokens"] += n_input_tokens
            n_used_tokens_dict[model]["n_output_tokens"] += n_output_tokens
        else:
            n_used_tokens_dict[model] = {
                "n_input_tokens": n_input_tokens,
                "n_output_tokens": n_output_tokens
            }
        try:
            self.set_user_attribute(user_id, "n_used_tokens", n_used_tokens_dict)
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Failed to update tokens for user {user_id}: {e}")
            raise

    def get_dialog_messages(self, user_id: int, dialog_id: Optional[str] = None) -> List[Dict]:
        """
        Get messages for a dialog.
        Args:
            user_id: Telegram user ID
            dialog_id: Dialog ID (optional, defaults to current dialog)
        Returns:
            List[Dict]: List of dialog messages
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        if not dialog_id:
            return []
        dialog_dict = self.dialog_collection.find_one({"_id": dialog_id, "user_id": user_id})
        if not dialog_dict:
            raise ValueError(f"Dialog {dialog_id} not found for user {user_id}")
        return dialog_dict.get("messages", [])

    def set_dialog_messages(self, user_id: int, dialog_messages: List[Dict], dialog_id: Optional[str] = None) -> None:
        """
        Set messages for a dialog.
        Args:
            user_id: Telegram user ID
            dialog_messages: List of dialog messages
            dialog_id: Dialog ID (optional, defaults to current dialog)
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        if not dialog_id:
            raise ValueError("No current dialog found")
        try:
            self.dialog_collection.update_one(
                {"_id": dialog_id, "user_id": user_id},
                {"$set": {"messages": dialog_messages}}
            )
            logger.debug(f"Updated messages for dialog {dialog_id} of user {user_id}")
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Failed to set dialog messages for user {user_id}: {e}")
            raise

    def get_user_dialogs(self, user_id: int) -> List[Dict]:
        """
        Get all dialogs for a user.
        Args:
            user_id: Telegram user ID
        Returns:
            List[Dict]: List of dialog metadata (id, start_time, chat_mode, model)
        """
        self.check_if_user_exists(user_id, raise_exception=True)
        dialogs = self.dialog_collection.find({"user_id": user_id}, {"_id": 1, "start_time": 1, "chat_mode": 1, "model": 1})
        return list(dialogs)

    def close(self):
        """Close the MongoDB client connection."""
        try:
            self.client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Failed to close MongoDB connection: {e}")

    def __del__(self):
        """Ensure MongoDB connection is closed when object is destroyed."""
        self.close()