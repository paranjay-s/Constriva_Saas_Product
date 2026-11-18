"""Typed failures of the PDF -> PlanJSON parser.

The parser either returns a complete, validated PlanJSON or raises one of these. It never
returns partial JSON. `code` is stable and meant for the API and the UI; `message` is safe
to show to a user.

They subclass ValueError because earlier callers of the parser catch ValueError.
"""


class PlanParseError(ValueError):
    code = "plan_parse_failed"

    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = list(details or [])

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class PdfInputError(PlanParseError):
    """The upload is not a readable PDF (or image)."""

    code = "invalid_pdf"


class NoFloorPlanError(PlanParseError):
    """The pages were read, but none of them shows a floor plan."""

    code = "no_floor_plan"


class ParserNotConfiguredError(PlanParseError):
    """No LLM provider or API key is configured."""

    code = "llm_not_configured"


class ParserUnavailableError(PlanParseError):
    """The LLM provider could not be reached or refused the request."""

    code = "llm_unavailable"


class PlanOutputInvalidError(PlanParseError):
    """The model's output was still invalid after every repair attempt.

    `details` holds the validation errors of the last attempt.
    """

    code = "llm_output_invalid"


class PlanNormalisationError(PlanParseError):
    """Valid model output could not be turned into a valid PlanJSON (a parser bug)."""

    code = "normalisation_failed"
