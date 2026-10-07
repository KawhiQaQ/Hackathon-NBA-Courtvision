const path = require('node:path');
const cdk = require('aws-cdk-lib');
const s3 = require('aws-cdk-lib/aws-s3');
const cloudfront = require('aws-cdk-lib/aws-cloudfront');
const origins = require('aws-cdk-lib/aws-cloudfront-origins');
const deployment = require('aws-cdk-lib/aws-s3-deployment');
const agentcore = require('aws-cdk-lib/aws-bedrockagentcore');
const lambda = require('aws-cdk-lib/aws-lambda');
const logs = require('aws-cdk-lib/aws-logs');
const iam = require('aws-cdk-lib/aws-iam');
const apigateway = require('aws-cdk-lib/aws-apigatewayv2');
const integrations = require('aws-cdk-lib/aws-apigatewayv2-integrations');

const app = new cdk.App();
const stack = new cdk.Stack(app, 'NbaTeam14Preflight', {
  env: { account: '214299441669', region: 'us-east-1' },
  description: 'Team14 CDK, CloudFront and AgentCore connectivity verification',
});
const runtime = new agentcore.Runtime(stack, 'ProbeAgent', {
  runtimeName: 'nba_team14_preflight',
  description: 'Connectivity probe only; no LLM inference or competition data',
  agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromCodeAsset({
    path: path.join(__dirname, 'agent'),
    runtime: agentcore.AgentCoreRuntime.PYTHON_3_13,
    entrypoint: ['main.py'],
    exclude: ['__pycache__', '*.pyc'],
  }),
  lifecycleConfiguration: {
    idleRuntimeSessionTimeout: cdk.Duration.seconds(60),
    maxLifetime: cdk.Duration.minutes(5),
  },
});
const proxy = new lambda.Function(stack, 'AgentProxy', {
  runtime: lambda.Runtime.PYTHON_3_13,
  architecture: lambda.Architecture.ARM_64,
  handler: 'handler.handler',
  code: lambda.Code.fromAsset(path.join(__dirname, 'api'), {
    exclude: ['__pycache__', '*.pyc'],
  }),
  timeout: cdk.Duration.seconds(30),
  memorySize: 256,
  reservedConcurrentExecutions: 2,
  environment: { AGENT_RUNTIME_ARN: runtime.agentRuntimeArn },
  logGroup: new logs.LogGroup(stack, 'ProxyLogs', {
    retention: logs.RetentionDays.ONE_WEEK,
    removalPolicy: cdk.RemovalPolicy.DESTROY,
  }),
});
runtime.grantInvokeRuntime(proxy);
proxy.addToRolePolicy(new iam.PolicyStatement({
  actions: ['bedrock-agentcore:StopRuntimeSession'],
  resources: [runtime.agentRuntimeArn, `${runtime.agentRuntimeArn}/runtime-endpoint/DEFAULT`],
}));
const api = new apigateway.HttpApi(stack, 'ProbeApi', { createDefaultStage: false });
api.addRoutes({
  path: '/api/agent',
  methods: [apigateway.HttpMethod.POST],
  integration: new integrations.HttpLambdaIntegration('AgentIntegration', proxy),
});
new apigateway.HttpStage(stack, 'ProbeApiStage', {
  httpApi: api,
  stageName: '$default',
  autoDeploy: true,
  throttle: { rateLimit: 1, burstLimit: 2 },
});
const bucket = new s3.Bucket(stack, 'Website', {
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  encryption: s3.BucketEncryption.S3_MANAGED,
  enforceSSL: true,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
const distribution = new cloudfront.Distribution(stack, 'Frontend', {
  comment: 'NBA Team14 preflight frontend',
  defaultRootObject: 'index.html',
  priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
  defaultBehavior: {
    origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
    compress: true,
  },
});
distribution.addBehavior('/api/*', new origins.HttpOrigin(
  cdk.Fn.select(2, cdk.Fn.split('/', api.apiEndpoint)),
), {
  viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
  allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
  cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
  originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
});
new deployment.BucketDeployment(stack, 'PublishFrontend', {
  sources: [deployment.Source.asset(path.join(__dirname, 'web'))],
  destinationBucket: bucket,
  distribution,
  distributionPaths: ['/*'],
});
new cdk.CfnOutput(stack, 'FrontendUrl', {
  value: `https://${distribution.distributionDomainName}`,
});
new cdk.CfnOutput(stack, 'BucketName', { value: bucket.bucketName });
new cdk.CfnOutput(stack, 'DistributionId', { value: distribution.distributionId });
new cdk.CfnOutput(stack, 'AgentRuntimeArn', { value: runtime.agentRuntimeArn });
new cdk.CfnOutput(stack, 'AgentRuntimeId', { value: runtime.agentRuntimeId });
new cdk.CfnOutput(stack, 'AgentApiUrl', {
  value: `https://${distribution.distributionDomainName}/api/agent`,
});
cdk.Tags.of(stack).add('Project', 'NBAHackathon');
cdk.Tags.of(stack).add('Purpose', 'Preflight');
cdk.Tags.of(stack).add('Team', 'Team14');
