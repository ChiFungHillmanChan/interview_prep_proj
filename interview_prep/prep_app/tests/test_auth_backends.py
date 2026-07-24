"""Sign-in must accept the address a user thinks of as their identity."""

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UsernameOrEmailLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hillman', email='owner@example.com', password='correct-horse-42'
        )

    def test_username_still_authenticates(self):
        self.assertEqual(authenticate(username='hillman', password='correct-horse-42'), self.user)

    def test_email_authenticates(self):
        self.assertEqual(
            authenticate(username='owner@example.com', password='correct-horse-42'), self.user
        )

    def test_email_match_is_case_insensitive(self):
        self.assertEqual(
            authenticate(username='OWNER@Example.COM', password='correct-horse-42'), self.user
        )

    def test_wrong_password_is_rejected_for_both_forms(self):
        self.assertIsNone(authenticate(username='hillman', password='wrong'))
        self.assertIsNone(authenticate(username='owner@example.com', password='wrong'))

    def test_unknown_identifier_is_rejected(self):
        self.assertIsNone(authenticate(username='nobody@example.com', password='correct-horse-42'))

    def test_inactive_user_cannot_sign_in_by_email(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(authenticate(username='owner@example.com', password='correct-horse-42'))

    def test_duplicate_email_authenticates_nobody(self):
        """auth_user.email has no unique constraint, so this state is reachable."""
        User.objects.create_user(
            username='impostor', email='owner@example.com', password='different-pass-99'
        )
        self.assertIsNone(authenticate(username='owner@example.com', password='correct-horse-42'))
        self.assertIsNone(authenticate(username='owner@example.com', password='different-pass-99'))
        # Each account still signs in by its own username.
        self.assertEqual(authenticate(username='hillman', password='correct-horse-42'), self.user)

    def test_username_wins_over_another_users_email(self):
        """A user must not be shadowed by someone registering their name as an email."""
        squatter = User.objects.create_user(
            username='shared@example.com', email='unrelated@example.com', password='squatter-pass-7'
        )
        self.user.email = 'shared@example.com'
        self.user.save(update_fields=['email'])
        self.assertEqual(
            authenticate(username='shared@example.com', password='squatter-pass-7'), squatter
        )
        self.assertIsNone(authenticate(username='shared@example.com', password='correct-horse-42'))

    def test_login_view_accepts_the_email(self):
        response = self.client.post(
            reverse('login'), {'username': 'owner@example.com', 'password': 'correct-horse-42'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))
