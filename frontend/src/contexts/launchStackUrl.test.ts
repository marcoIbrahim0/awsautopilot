import { describe, expect, it } from 'vitest';

import {
  buildCloudFormationLaunchStackUrl,
  extractTemplateUrlFromLaunchUrl,
} from './launchStackUrl';

describe('launchStackUrl helpers', () => {
  it('extracts the template URL from an existing launch URL', () => {
    expect(
      extractTemplateUrlFromLaunchUrl(
        'https://eu-north-1.console.aws.amazon.com/cloudformation/home?region=eu-north-1#/stacks/create/review?templateURL=https%3A%2F%2Fexample.com%2Fread-role.yaml&stackName=SecurityAutopilotReadRole',
      ),
    ).toBe('https://example.com/read-role.yaml');
  });

  it('still extracts the template URL from legacy create/template links', () => {
    expect(
      extractTemplateUrlFromLaunchUrl(
        'https://eu-north-1.console.aws.amazon.com/cloudformation/home?region=eu-north-1#/stacks/create/template?templateURL=https%3A%2F%2Fexample.com%2Fread-role.yaml&stackName=SecurityAutopilotReadRole',
      ),
    ).toBe('https://example.com/read-role.yaml');
  });

  it('still extracts the template URL from legacy stacks/new links', () => {
    expect(
      extractTemplateUrlFromLaunchUrl(
        'https://eu-north-1.console.aws.amazon.com/cloudformation/home?region=eu-north-1#/stacks/new?templateURL=https%3A%2F%2Fexample.com%2Fread-role.yaml&stackName=SecurityAutopilotReadRole',
      ),
    ).toBe('https://example.com/read-role.yaml');
  });

  it('preserves existing CloudFormation parameters when only the stack name changes', () => {
    const launchUrl = buildCloudFormationLaunchStackUrl({
      existingLaunchUrl:
        'https://eu-north-1.console.aws.amazon.com/cloudformation/home?region=eu-north-1#/stacks/create/review?templateURL=https%3A%2F%2Fexample.com%2Fread-role.yaml&stackName=SecurityAutopilotReadRole&param_SaaSAccountId=029037611564&param_ExternalId=ext-123&param_SaaSExecutionRoleArns=arn%3Aaws%3Aiam%3A%3A029037611564%3Arole%2Fapi%2Carn%3Aaws%3Aiam%3A%3A029037611564%3Arole%2Fworker',
      region: 'eu-north-1',
      stackName: 'SecurityAutopilotReadRole-Custom',
    });

    expect(launchUrl).toContain('stackName=SecurityAutopilotReadRole-Custom');
    expect(launchUrl).toContain('param_SaaSAccountId=029037611564');
    expect(launchUrl).toContain('param_ExternalId=ext-123');
    expect(launchUrl).toContain('param_SaaSExecutionRoleArns=');
    expect(launchUrl).toContain('#/stacks/create/review?');
    expect(decodeURIComponent(launchUrl || '')).toContain(
      'param_SaaSExecutionRoleArns=arn:aws:iam::029037611564:role/api,arn:aws:iam::029037611564:role/worker',
    );
  });

  it('falls back to provided template URL and parameters when no launch URL exists', () => {
    const launchUrl = buildCloudFormationLaunchStackUrl({
      fallbackTemplateUrl: 'https://example.com/write-role.yaml',
      region: 'eu-north-1',
      stackName: 'SecurityAutopilotWriteRole',
      fallbackStackName: 'SecurityAutopilotWriteRole',
      fallbackParams: {
        param_SaaSAccountId: '029037611564',
        param_ExternalId: 'ext-123',
      },
    });

    expect(launchUrl).toContain('templateURL=https%3A%2F%2Fexample.com%2Fwrite-role.yaml');
    expect(launchUrl).toContain('stackName=SecurityAutopilotWriteRole');
    expect(launchUrl).toContain('param_SaaSAccountId=029037611564');
    expect(launchUrl).toContain('param_ExternalId=ext-123');
    expect(launchUrl).toContain('#/stacks/create/review?');
  });
});
