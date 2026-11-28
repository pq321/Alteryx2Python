from __future__ import annotations

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, child, text, attributes


def parse_email_config(raw_config):
    attachments = as_list(child(child(raw_config, 'Attachments'), 'Attachment'))
    supported = {'From','To','Subject','Body','Attachments','SMTPServer','container_id','child_node_ids','annotation'}
    native = 'SMTPServerName' in raw_config
    if native:
        supported |= {'SMTPServerName', 'SMTPAuth', 'Port', 'Encryption', 'Enabled', 'BodyIsField'}
    unsupported = sorted(set(raw_config) - supported)
    def enabled(config, tag, default=False):
        element = child(config, tag)
        return str(attributes(element).get('value', text(element, str(default)))).lower() == 'true'

    if native and (not enabled(raw_config, 'Enabled', True) or enabled(raw_config, 'BodyIsField')):
        unsupported.append('native Email requires enabled literal body')
    if native and (enabled(raw_config, 'SMTPAuth') or text(child(raw_config, 'Encryption'), 'None') != 'None'):
        unsupported.append('native Email SMTP authentication or encryption')
    for name in ('From','To','Subject','Body'):
        attrs = attributes(child(raw_config,name))
        if any(str(value).lower() in {'true','1'} for key,value in attrs.items() if key.lower() in {'field','isfield','fromfield'}):
            unsupported.append(name + ':dynamic-field')
    paths = []
    for attachment in attachments:
        if native and isinstance(attachment, dict) and 'Value' in attachment:
            if enabled(attachment, 'ValueIsField'):
                unsupported.append('Attachment:dynamic-field')
            paths.append(text(child(attachment, 'Value')))
        elif attributes(attachment):
            unsupported.append('Attachment:options')
        else:
            paths.append(text(attachment))
    normalized = {
        'from': text(child(raw_config, 'From')),
        'to': text(child(raw_config, 'To')),
        'subject': text(child(raw_config, 'Subject')),
        'body': text(child(raw_config, 'Body'), 'Report'),
        'attachments': paths,
        'smtp_server': text(child(raw_config, 'SMTPServer')),
        'unsupported_options': unsupported,
    }
    if native:
        normalized.update(
            plain_body=True,
            smtp_server=text(child(raw_config, 'SMTPServerName')),
            smtp_port=text(child(raw_config, 'Port'), '25'),
        )
    return ToolParserResult(normalized_config=normalized)
