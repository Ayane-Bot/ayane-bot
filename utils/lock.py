import asyncio
from utils.exceptions import UserLocked


class UserLock:
    def __init__(
            self,
            user,
            error_message=
            "You probably clicked on a button that is waiting for your answer,"
            "please firstly cancel the operation.",
    ):
        self.user = user
        self.error_message = error_message
        self.lock = asyncio.Lock()

    def __call__(self, bot):
        bot.add_user_lock(self)
        return self.lock

    def locked(self):
        return self.lock.locked()

    def release(self):
        self.lock.release()

    @property
    def error(self):
        return UserLocked(message=self.error_message)
