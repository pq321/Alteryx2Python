# Download Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- read the request URL from a configured input field
- support `String` output mode
- support static headers from the workflow configuration
- support field-backed request bodies for `Payload/QueryStringBodyMode=Field`
- append `DownloadData` and `DownloadHeaders` to the input rows
- support injected transports through config or `WorkflowContext.runtime_config`

Deferred semantics:

- default live HTTP execution unless `allow_network_downloads=True` is explicitly set
- binary/blob output modes
- dynamic headers sourced from input fields
- multipart uploads and download-to-file modes
- exact Alteryx retry, throttling, and error-row behavior
- golden-output certification against official examples
