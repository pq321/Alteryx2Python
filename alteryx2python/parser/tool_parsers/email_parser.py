from __future__ import annotations

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, child, text, attributes


def parse_email_config(raw_config):
    attachments = as_list(child(child(raw_config, 'Attachments'), 'Attachment'))
    supported = {'From','To','Subject','Body','Attachments','SMTPServer','container_id','child_node_ids','annotation'}
    unsupported = sorted(set(raw_config) - supported)
    for name in ('From','To','Subject','Body'):
        attrs = attributes(child(raw_config,name))
        if any(str(value).lower() in {'true','1'} for key,value in attrs.items() if key.lower() in {'field','isfield','fromfield'}):
            unsupported.append(name + ':dynamic-field')
    for attachment in attachments:
        if attributes(attachment):
            unsupported.append('Attachment:options')
    return ToolParserResult(normalized_config={
        'from': text(child(raw_config, 'From')),
        'to': text(child(raw_config, 'To')),
        'subject': text(child(raw_config, 'Subject')),
        'body': text(child(raw_config, 'Body'), 'Report'),
        'attachments': [text(item) for item in attachments],
        'smtp_server': text(child(raw_config, 'SMTPServer')),
        'unsupported_options': unsupported,
    })
