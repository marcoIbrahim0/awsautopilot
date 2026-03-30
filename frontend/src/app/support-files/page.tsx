import { redirect } from 'next/navigation';

export default function SupportFilesPage() {
  redirect('/help?tab=files');
}
