import { redirect } from 'next/navigation';

export default function BaselineReportPage() {
  redirect('/settings?tab=baseline-report');
}
