import { redirect, notFound } from "next/navigation";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user";
import { isSalesOnly } from "@/shared/lib/roles";
import {
  fetchQuoteDetail,
  fetchQuoteItems,
  fetchQuoteInvoices,
  fetchQuoteComments,
  fetchQuoteCalcVariables,
  fetchStageDeadline,
  fetchDealIdForQuote,
  canAccessQuote,
  ROLE_ALLOWED_STEPS,
  ROLE_EDITABLE_STEPS,
  STATUS_TO_STEP,
} from "@/entities/quote";
import type { QuoteStep, StageDeadlineData } from "@/entities/quote";
import { QuoteDetailShell } from "@/features/quotes/ui/quote-detail-shell";
import { QuoteStatusRail } from "@/features/quotes/ui/quote-status-rail";
import { QuoteStepContent } from "@/features/quotes/ui/quote-step-content";
import { ChatWrapper } from "@/features/quotes/ui/chat-panel/chat-wrapper";
import { UseCollapsedSidebar } from "@/features/quotes/ui/use-collapsed-sidebar";
import { fetchOrgMembers } from "@/features/messages/queries";
import { fetchDocumentCount } from "@/features/quotes/ui/documents-step/queries";
import { fetchQuoteContextData } from "@/features/quotes/ui/context-panel/queries";
import { fetchEntityNotes } from "@/entities/entity-note/queries";

function getDefaultStep(roles: string[]): QuoteStep {
  for (const role of roles) {
    const steps = ROLE_ALLOWED_STEPS[role];
    if (steps?.length) return steps[0];
  }
  return "sales";
}

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ step?: string }>;
}

export default async function QuoteDetailPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { step } = await searchParams;

  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  // Sales users need salesGroupId to resolve head_of_sales group access.
  const salesGroupId = isSalesOnly(user.roles)
    ? await fetchUserSalesGroupId(user.id, user.orgId)
    : null;
  const accessUser = {
    id: user.id,
    roles: user.roles,
    orgId: user.orgId,
    salesGroupId,
  };

  const [
    quote,
    items,
    invoices,
    comments,
    calcVariables,
    orgMembers,
    documentCount,
    dealId,
    hasAccess,
    contextData,
    quoteNotes,
  ] = await Promise.all([
    fetchQuoteDetail(id),
    fetchQuoteItems(id),
    fetchQuoteInvoices(id),
    fetchQuoteComments(id),
    fetchQuoteCalcVariables(id),
    fetchOrgMembers(user.orgId),
    fetchDocumentCount(id),
    fetchDealIdForQuote(id),
    canAccessQuote(id, accessUser),
    fetchQuoteContextData(id),
    fetchEntityNotes("quote", id),
  ]);

  if (!quote || !hasAccess) notFound();

  const userRoles = user.roles;
  const isAdmin = userRoles.includes("admin");

  // Fetch stage deadline data (depends on quote being loaded)
  const workflowStatusForDeadline = quote.workflow_status ?? "draft";
  const stageDeadline: StageDeadlineData = await fetchStageDeadline(
    id,
    user.orgId,
    workflowStatusForDeadline
  );

  // Determine allowed steps for this user
  const allowedSteps = isAdmin
    ? ROLE_ALLOWED_STEPS.admin
    : [...new Set(userRoles.flatMap((r) => ROLE_ALLOWED_STEPS[r] ?? []))];

  // Resolve active step: requested > role-based default
  const requestedStep = step as QuoteStep | undefined;
  const activeStep: QuoteStep =
    requestedStep && allowedSteps.includes(requestedStep)
      ? requestedStep
      : getDefaultStep(userRoles);

  // Determine if this step is read-only for the user (can view but not edit)
  const editableSteps = isAdmin
    ? allowedSteps
    : [...new Set(userRoles.flatMap((r) => ROLE_EDITABLE_STEPS[r] ?? ROLE_ALLOWED_STEPS[r] ?? []))];
  const isReadOnly = allowedSteps.length > 0 && !editableSteps.includes(activeStep);

  // Current workflow position (for rail highlighting)
  const workflowStatus = quote.workflow_status ?? "draft";
  const currentWorkflowStep = STATUS_TO_STEP[workflowStatus] ?? "sales";

  return (
    <>
      <UseCollapsedSidebar />
      <QuoteDetailShell
        quote={quote}
        documentCount={documentCount}
        activeStep={activeStep}
        userRoles={userRoles}
        contextData={contextData}
        stepContent={
          <QuoteStepContent
            key="step"
            quote={quote}
            items={items}
            invoices={invoices}
            activeStep={activeStep}
            userRoles={userRoles}
            userId={user.id}
            calcVariables={calcVariables}
            dealId={dealId}
            isReadOnly={isReadOnly}
            quoteNotes={quoteNotes}
          />
        }
        chat={
          <ChatWrapper
            key="chat"
            quoteId={id}
            idnQuote={quote.idn_quote}
            userId={user.id}
            orgId={user.orgId}
            initialComments={comments}
            orgMembers={orgMembers}
          />
        }
        rail={
          <QuoteStatusRail
            key="rail"
            activeStep={activeStep}
            currentWorkflowStep={currentWorkflowStep}
            allowedSteps={allowedSteps}
            isAdmin={isAdmin}
            quoteId={id}
            workflowStatus={workflowStatus}
            stageDeadline={stageDeadline}
          />
        }
      />
    </>
  );
}
