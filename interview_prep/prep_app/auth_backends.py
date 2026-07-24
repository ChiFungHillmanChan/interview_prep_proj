"""Authentication backend allowing sign-in with either username or email."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate against `username`, falling back to a unique `email` match.

    Django's stock ModelBackend only ever looks at USERNAME_FIELD, so an account
    created with `username='hillman', email='someone@example.com'` cannot sign in
    with the address the user thinks of as their identity.

    Two properties matter more than the convenience:

    * `auth_user.email` carries no uniqueness constraint. Registration rejects
      duplicates, but social sign-in and `createsuperuser` do not, so a duplicate
      is reachable. An ambiguous address must never authenticate anyone, or
      whichever row sorts first would silently own the address.
    * An exact username match always wins over an email match, so a user cannot
      be shadowed by someone else registering their username as an email.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        user = self._resolve(UserModel, username)
        if user is None:
            # Same dummy hash ModelBackend runs, so a missing account cannot be
            # distinguished from a wrong password by response time.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def _resolve(UserModel, identifier):
        username_field = UserModel.USERNAME_FIELD
        exact = UserModel._default_manager.filter(**{f'{username_field}__iexact': identifier})
        matches = list(exact[:2])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Ambiguous username; refuse rather than guess.
            return None

        if '@' not in identifier:
            return None
        by_email = list(UserModel._default_manager.filter(Q(email__iexact=identifier))[:2])
        return by_email[0] if len(by_email) == 1 else None
