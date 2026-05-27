import type { components } from "./api.generated";

import type {
  BacktestConfig,
  ComparePayload,
  DataAlert,
  DataSource,
  FeaturedDigest,
  GeneratedReportFile,
  GenerateReportRequest,
  GenerateReportResponse,
  OptionsPayload,
  OverviewPayload,
  ReportEntry,
  RunDetailPayload,
  RunRow,
  RunRowSummary,
  UniverseTimelinePayload,
} from "./api";

type Schema = components["schemas"];

type Assert<T extends true> = T;
type IsAssignable<From, To> = [From] extends [To] ? true : false;

export type ApiContractAssertions = [
  Assert<IsAssignable<BacktestConfig, Schema["BacktestConfig"]>>,
  Assert<IsAssignable<Schema["ComparePayload"], ComparePayload>>,
  Assert<IsAssignable<Schema["DataAlert"], DataAlert>>,
  Assert<IsAssignable<Schema["DataSource"], DataSource>>,
  Assert<IsAssignable<Schema["FeaturedDigest"], FeaturedDigest>>,
  Assert<IsAssignable<Schema["GeneratedReportFile"], GeneratedReportFile>>,
  Assert<IsAssignable<GenerateReportRequest, Schema["GenerateReportRequest"]>>,
  Assert<IsAssignable<Schema["GenerateReportResponse"], GenerateReportResponse>>,
  Assert<IsAssignable<Schema["OptionsPayload"], OptionsPayload>>,
  Assert<IsAssignable<Schema["OverviewPayload"], OverviewPayload>>,
  Assert<IsAssignable<Schema["ReportEntry"], ReportEntry>>,
  Assert<IsAssignable<Schema["RunDetailPayload"], RunDetailPayload>>,
  Assert<IsAssignable<Schema["RunRow"], RunRow>>,
  Assert<IsAssignable<Schema["RunRowSummary"], RunRowSummary>>,
  Assert<IsAssignable<Schema["UniverseTimelinePayload"], UniverseTimelinePayload>>,
];
