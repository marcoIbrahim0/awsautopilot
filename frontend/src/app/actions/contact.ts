'use server';

export async function submitContactForm(formData: FormData) {
  const data = {
    message: formData.get('message'),
    name: formData.get('name'),
    email: formData.get('email'),
    company: formData.get('company'),
    phone: formData.get('phone'),
  };

  const endpoint = process.env.CONTACT_LAMBDA_URL;
  
  if (!endpoint) {
    console.warn("CONTACT_LAMBDA_URL is not set. Mocking successful submission for:", data);
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, mocked: true };
  }

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      throw new Error(`Failed to submit: ${res.statusText}`);
    }

    return { success: true };
  } catch (error) {
    console.error("Error submitting contact form:", error);
    return { success: false, error: 'Failed to submit form' };
  }
}
