class KIPRISVerificationRequired(RuntimeError):
    """Raised when code tries to use the real KIPRIS client before fixture verification."""


class KIPRISClient:
    """Placeholder boundary for the real client.

    The real implementation must be based on raw fixtures produced by
    scripts/verify_kipris_api.py, because KIPRIS Plus field names differ
    across operations and some endpoints respond as XML.
    """

    async def search_patents(self, *_args, **_kwargs):
        raise KIPRISVerificationRequired(
            "Run scripts/verify_kipris_api.py with KIPRIS_API_KEY and inspect fixtures before implementing KIPRISClient."
        )

    async def get_patent_detail(self, *_args, **_kwargs):
        raise KIPRISVerificationRequired(
            "Run scripts/verify_kipris_api.py with KIPRIS_API_KEY and inspect fixtures before implementing KIPRISClient."
        )
