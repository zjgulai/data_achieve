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


class ReportSendAuthorizationError(ServiceError):
    message = "report_send_authorization_required"


class ReportSendConfirmationRequiredError(ServiceError):
    message = "report_send_confirmation_required"


class ReportSubscriptionNotFoundError(ServiceError):
    message = "Report subscription not found"


class ReportSubscriptionRunNotFoundError(ServiceError):
    message = "Report subscription run not found"


class ReportSubscriptionRunAuthorizationError(ServiceError):
    message = "report_subscription_run_authorization_required"


class ReportSubscriptionRunConfirmationRequiredError(ServiceError):
    message = "report_subscription_run_confirmation_required"


class ReportSubscriptionRetryAuthorizationError(ServiceError):
    message = "report_subscription_retry_authorization_required"


class ReportSubscriptionRetryConfirmationRequiredError(ServiceError):
    message = "report_subscription_retry_confirmation_required"


class ReportSubscriptionRunRetryNotAllowedError(ServiceError):
    message = "Only failed or partially successful report subscription runs can be retried"


class AlertRuleNotFoundError(ServiceError):
    message = "Alert rule not found"


class AlertEventNotFoundError(ServiceError):
    message = "Alert event not found"


class NotificationNotFoundError(ServiceError):
    message = "Notification not found"


class EmailChannelTestAuthorizationError(ServiceError):
    message = "email_channel_test_authorization_required"


class EmailChannelTestConfirmationRequiredError(ServiceError):
    message = "email_channel_test_confirmation_required"


class EmailProviderLiveGateAuthorizationError(ServiceError):
    message = "email_provider_live_gate_authorization_required"


class EmailProviderLiveGateConfirmationRequiredError(ServiceError):
    message = "email_provider_live_gate_confirmation_required"


class EmailProviderLiveSendAuthorizationError(ServiceError):
    message = "email_provider_live_send_authorization_required"


class EmailProviderLiveSendConfirmationRequiredError(ServiceError):
    message = "email_provider_live_send_confirmation_required"


class EmailProviderLiveSendIdempotencyRequiredError(ServiceError):
    message = "email_provider_live_send_idempotency_key_required"


class EmailProviderLiveGateRunNotFoundError(ServiceError):
    message = "email_provider_live_gate_run_not_found"


class CapabilityCatalogLoadError(ServiceError):
    message = "capability_catalog_load_failed"


class CapabilityCatalogUnknownPlatformError(ServiceError):
    message = "capability_catalog_unknown_platform"


class CapabilityImplementationNotFoundError(ServiceError):
    message = "capability_implementation_not_found"


class SocialProviderCatalogLoadError(ServiceError):
    message = "social_provider_catalog_load_failed"


class SocialProviderUnknownPlatformError(ServiceError):
    message = "social_provider_unknown_platform"


class SocialProviderReadinessAuthorizationError(ServiceError):
    message = "social_provider_readiness_authorization_required"


class SocialProviderGateAuthorizationError(ServiceError):
    message = "social_provider_gate_authorization_required"
