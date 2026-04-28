# Learnings from cuenta_regresiva
*2026-04-21*

## Pattern: Modular API Architecture
The separation of concerns into distinct modules for Configuration, Storage (Data), Business Logic (Services), and API is a robust pattern for building maintainable ASP.NET Core applications. It promotes clear responsibilities and testability.

## Pattern: Interface-based Notification Service
Defining an `INotificationSender` interface for the alerting module is an effective way to decouple notification logic. This allows for flexible implementation of different notification methods (e.g., email, Slack) that can be swapped without altering the core services that use them.

## Anti-pattern: Ignoring User Requirements for Architecture
The most critical failure was implementing a complex error-monitoring web API architecture when the user explicitly requested a simple Windows desktop countdown timer. The developer profile must learn to validate any proposed architecture against the core user request before proceeding.

## Anti-pattern: Inappropriate Complexity
Applying an enterprise-level web API pattern with a database and alerting services to a simple desktop utility is a severe case of over-engineering. The profile should be able to match the complexity of the solution to the complexity of the problem.

## Preference: Defaults to Web API Backend
The profile demonstrates a strong preference for building ASP.NET Core Web API backends, even when the user's request was for a desktop application. It seems to lack knowledge or preference for UI frameworks like MAUI, WPF, or WinForms.

## Preference: Prefers Layered/N-Tier Structure
The design shows a clear preference for a classic layered architecture, separating the application into Data (Repositories), Business Logic (Services), and Presentation (API Controllers) layers. This is a common and solid pattern in the .NET world.

## Knowledge Suggestion
Add knowledge to differentiate between application types (Desktop, Web, Mobile) and select the appropriate .NET framework. For a 'Windows application' request, frameworks like .NET MAUI or WPF should be considered instead of ASP.NET Core.
