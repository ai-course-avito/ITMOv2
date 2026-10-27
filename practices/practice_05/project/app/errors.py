"""Safe error vocabulary shared by the service and HTTP boundary."""

ERRORS = {
    'UNSUPPORTED_MEDIA_TYPE': (415, 'Передайте запрос в формате JSON.'),
    'INVALID_JSON': (400, 'Не удалось прочитать JSON запроса.'),
    'INVALID_REQUEST': (422, 'Передайте только поле diff с непустой строкой.'),
    'DIFF_TOO_LARGE': (413, 'Diff превышает лимит 20 000 символов.'),
    'INVALID_DIFF': (422, 'Вставьте текстовый unified diff с изменёнными строками.'),
    'UNSUPPORTED_DIFF': (422, 'Этот формат diff или пути пока не поддерживается.'),
    'MODEL_NOT_CONFIGURED': (503, 'Модель не настроена на сервере.'),
    'MODEL_TIMEOUT': (504, 'Анализ не завершился за 10 секунд. Повторите вручную позже.'),
    'MODEL_UNAVAILABLE': (502, 'Сервис анализа временно недоступен. Повторите вручную позже.'),
    'INVALID_MODEL_OUTPUT': (502, 'Ответ анализа не прошёл проверку. Повторите вручную.'),
    'INTERNAL_ERROR': (500, 'Не удалось выполнить анализ. Сохраните идентификатор запроса.'),
}


class ReviewError(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'INTERNAL_ERROR'
        self.status, self.message = ERRORS[self.code]
        super().__init__(self.message)
