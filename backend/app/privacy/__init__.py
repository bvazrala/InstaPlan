"""The privacy layer. Everything that decides who can see private data lives in this package.

Rules (enforced in code and tested in tests/test_privacy.py):
1. The server decides who sees what. Private routes use /me/ and never take a user id from the client.
2. Private data is stored in its own tables, encrypted (crypto.py).
3. Group requests to Muse carry only a GroupContext; private check-in requests carry one member's PrivateContext.
   They are separate, stateless requests in separate modules (integrations/muse_group.py vs muse_private.py).
4. Group views show aggregates and ranks, never one person's value.
"""
