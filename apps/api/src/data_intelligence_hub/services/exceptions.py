from __future__ import annotations


class ServiceError(Exception):
    message = "Service error"


class DuplicateEmailError(ServiceError):
    message = "Email already registered"


class InvalidCredentialsError(ServiceError):
    message = "Invalid email or password"


class WorkspaceNotFoundError(ServiceError):
    message = "Workspace not found"


class ProjectNotFoundError(ServiceError):
    message = "Project not found"


class CollectorNotFoundError(ServiceError):
    message = "Collector not found"


class CollectorConfigError(ServiceError):
    message = "Collector config is invalid"


class SourceNotFoundError(ServiceError):
    message = "Source not found"


class TaskNotFoundError(ServiceError):
    message = "Task not found"


class TaskAlreadyRunningError(ServiceError):
    message = "Task is already running"


class TaskNotRunnableError(ServiceError):
    message = "Task is not enabled"


class RawRecordNotFoundError(ServiceError):
    message = "Raw record not found"


class EntityNotFoundError(ServiceError):
    message = "Entity not found"


class SignalNotFoundError(ServiceError):
    message = "Signal not found"


class SignalSnapshotCompareNotAvailableError(ServiceError):
    message = "Signal snapshot compare is not available"


class IntelligenceNotFoundError(ServiceError):
    message = "Intelligence item not found"


class ReportNotFoundError(ServiceError):
    message = "Report not found"


class ReportSubscriptionNotFoundError(ServiceError):
    message = "Report subscription not found"


class ReportSubscriptionRunNotFoundError(ServiceError):
    message = "Report subscription run not found"


class ReportSubscriptionRunRetryNotAllowedError(ServiceError):
    message = "Only failed or partially successful report subscription runs can be retried"


class AlertRuleNotFoundError(ServiceError):
    message = "Alert rule not found"


class NotificationNotFoundError(ServiceError):
    message = "Notification not found"
