from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def coding_execution_disabled(request, question_id):
    return JsonResponse({
        'status': 'disabled',
        'message': (
            'Code execution is disabled because AceInterview does not yet have an isolated sandbox. '
            'Use the coding discussion to explain, review, test, or write pseudocode.'
        ),
    }, status=410)
