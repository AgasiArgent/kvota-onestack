import { redirect, notFound } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchQuoteDetail,
  fetchQuoteItems,
  fetchQuoteInvoices,
  fetchQuoteComments,
  fetchQuoteCalcVariables,
  ROLE_ALLOWED_STEPS,
  STATUS_TO_STEP,
} from "@/entities/quote";
import type { QuoteStep } from "@/entities/quote";
import { QuoteStickyHeader } from "@/features/quotes/ui/quote-sticky-header";
import { QuoteStatusRail } from "@/features/quotes/ui/quote-status-rail";
import { QuoteStepContent } from "@/features/quotes/ui/quote-step-content";
import { ChatWrapper } from "@/features/quotes/ui/chat-panel/chat-wrapper";
import { UseCollapsedSidebar } from "@/features/quotes/ui/use-collapsed-sidebar";

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

  const [quote, items, invoices, comments, calcVariables] = await Promise.all([
    fetchQuoteDetail(id),
    fetchQuoteItems(id),
    fetchQuoteInvoices(id),
    fetchQuoteComments(id),
    fetchQuoteCalcVariables(id),
  ]);

  if (!quote) notFound();

  const userRoles = user.roles;
  const isAdmin = userRoles.includes("admin");

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

  // Current workflow position (for rail highlighting)
  const workflowStatus = quote.workflow_status ?? "draft";
  const currentWorkflowStep = STATUS_TO_STEP[workflowStatus] ?? "sales";

  return (
    <div className="flex flex-col h-full">
      <UseCollapsedSidebar />
      <QuoteStickyHeader quote={quote} isAdmin={isAdmin} />
      <div className="flex flex-1 min-h-0">
        <QuoteStepContent
          quote={quote}
          items={items}
          invoices={invoices}
          activeStep={activeStep}
          userRoles={userRoles}
          calcVariables={calcVariables}
        />
        <QuoteStatusRail
          activeStep={activeStep}
          currentWorkflowStep={currentWorkflowStep}
          allowedSteps={allowedSteps}
          isAdmin={isAdmin}
          quoteId={id}
          workflowStatus={workflowStatus}
        />
      </div>
      <ChatWrapper
        quoteId={id}
        idnQuote={quote.idn_quote}
        userId={user.id}
        initialComments={comments}
      />
    </div>
  );
}
