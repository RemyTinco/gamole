CREATE TYPE "public"."workflow_status" AS ENUM('INITIALIZED', 'CONTEXT_RETRIEVED', 'DRAFT_GENERATED', 'QA_REVIEWED', 'DEV_REVIEWED', 'PO_REVIEWED', 'SUPERVISOR_REFINED', 'QUALITY_EVALUATED', 'APPROVED_FINAL_AI', 'USER_EDITING', 'READY_TO_PUSH', 'PUSHED_TO_LINEAR', 'FAILED');--> statement-breakpoint
CREATE TYPE "public"."document_version_type" AS ENUM('AI_FINAL', 'USER_EDITED');--> statement-breakpoint
CREATE TYPE "public"."push_mode" AS ENUM('create', 'update');--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "workspaces" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"template_json" jsonb,
	"settings_json" jsonb,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "linear_connections" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workspace_id" uuid NOT NULL,
	"token_ref" text NOT NULL,
	"linear_org_id" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workflows" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workspace_id" uuid NOT NULL,
	"status" "workflow_status" DEFAULT 'INITIALIZED' NOT NULL,
	"input_text" text NOT NULL,
	"input_mode" text DEFAULT 'form' NOT NULL,
	"target_team_id" text NOT NULL,
	"target_project_id" text,
	"quality_score" real,
	"quality_flags_json" jsonb,
	"retrieval_stats_json" jsonb,
	"agent_rounds" integer DEFAULT 0 NOT NULL,
	"state_json" jsonb,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "document_versions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workflow_id" uuid NOT NULL,
	"type" "document_version_type" NOT NULL,
	"content_markdown" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "agent_runs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workflow_id" uuid NOT NULL,
	"agent_name" text NOT NULL,
	"round_number" integer DEFAULT 1 NOT NULL,
	"latency_ms" integer,
	"token_in" integer,
	"token_out" integer,
	"success" boolean DEFAULT true NOT NULL,
	"error_type" text,
	"critique_markdown" text,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "linear_push_events" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workflow_id" uuid NOT NULL,
	"linear_issue_id" text NOT NULL,
	"mode" "push_mode" NOT NULL,
	"pushed_at" timestamp DEFAULT now() NOT NULL,
	"token_ref" text NOT NULL,
	"result_json" jsonb
);
--> statement-breakpoint
CREATE TABLE "linear_issues_cache" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"linear_id" text NOT NULL,
	"team_id" text NOT NULL,
	"title" text NOT NULL,
	"description" text,
	"embedding" vector(768),
	"synced_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "linear_issues_cache_linear_id_unique" UNIQUE("linear_id")
);
--> statement-breakpoint
CREATE TABLE "codebase_chunks" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"repo_name" text NOT NULL,
	"file_path" text NOT NULL,
	"language" text,
	"chunk_text" text NOT NULL,
	"domain" text,
	"artifact_type" text,
	"embedding" vector(768),
	"last_indexed_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "audit_log" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workflow_id" uuid,
	"event_type" text NOT NULL,
	"payload_json" jsonb,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "workspaces" ADD CONSTRAINT "workspaces_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "linear_connections" ADD CONSTRAINT "linear_connections_workspace_id_workspaces_id_fk" FOREIGN KEY ("workspace_id") REFERENCES "public"."workspaces"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workflows" ADD CONSTRAINT "workflows_workspace_id_workspaces_id_fk" FOREIGN KEY ("workspace_id") REFERENCES "public"."workspaces"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_versions" ADD CONSTRAINT "document_versions_workflow_id_workflows_id_fk" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_workflow_id_workflows_id_fk" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "linear_push_events" ADD CONSTRAINT "linear_push_events_workflow_id_workflows_id_fk" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "linear_issues_embedding_idx" ON "linear_issues_cache" USING hnsw ("embedding" vector_cosine_ops);--> statement-breakpoint
CREATE INDEX "codebase_chunks_embedding_idx" ON "codebase_chunks" USING hnsw ("embedding" vector_cosine_ops);