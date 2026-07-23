import { test, expect } from '@playwright/test';

test.describe('RentMasseur Visitor App', () => {
  test('loads and displays header', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.logo-text')).toHaveText('RentMasseur');
    await expect(page.locator('.logo-sub')).toHaveText('Find your masseur');
  });

  test('displays hero section with title', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.hero h1')).toContainText('Professional Massage');
    await expect(page.locator('.hero h1 span')).toHaveText('On Demand');
  });

  test('shows specialty filter pills', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.spec-pill')).toHaveCount(8);
    await expect(page.locator('.spec-pill').first()).toContainText('Swedish');
  });

  test('filters masseurs by specialty', async ({ page }) => {
    await page.goto('/');
    // Wait for loading to finish
    await page.waitForSelector('.card', { timeout: 5000 });
    const initialCount = await page.locator('.card').count();
    expect(initialCount).toBe(6);

    // Click Deep Tissue filter
    await page.locator('.spec-pill', { hasText: 'Deep Tissue' }).click();
    const filteredCount = await page.locator('.card').count();
    expect(filteredCount).toBeLessThan(initialCount);

    // Clear filter
    await page.locator('.spec-pill', { hasText: 'Deep Tissue' }).click();
    const restoredCount = await page.locator('.card').count();
    expect(restoredCount).toBe(6);
  });

  test('searches masseurs by name', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('#search').fill('Marcus');
    const count = await page.locator('.card').count();
    expect(count).toBe(1);
    await expect(page.locator('.card').first()).toContainText('Marcus');
  });

  test('opens masseur detail modal', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('.card').first().click();
    await expect(page.locator('.modal')).toBeVisible();
    await expect(page.locator('.modal-name')).toBeVisible();
    await expect(page.locator('.btn-book')).toBeVisible();
  });

  test('booking requires date and time', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('.card').first().click();
    await expect(page.locator('#btn-book')).toBeDisabled();
    
    await page.locator('#book-date').fill('2026-08-01');
    await page.locator('#book-time').selectOption('10:00 AM');
    await expect(page.locator('#btn-book')).toBeEnabled();
  });

  test('completes booking flow', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('.card').first().click();
    await page.locator('#book-date').fill('2026-08-01');
    await page.locator('#book-time').selectOption('10:00 AM');
    await page.locator('#btn-book').click();
    
    await expect(page.locator('.booked')).toBeVisible();
    await expect(page.locator('.booked b')).toHaveText('Booking Confirmed!');
  });

  test('closes modal on backdrop click', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('.card').first().click();
    await expect(page.locator('.modal')).toBeVisible();
    
    await page.locator('#modal-bg').click({ position: { x: 5, y: 5 } });
    await expect(page.locator('.modal')).not.toBeVisible();
  });

  test('shows empty state when no results', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    await page.locator('#search').fill('xyznonexistent');
    await expect(page.locator('.empty')).toBeVisible();
    await expect(page.locator('.empty')).toContainText('No masseurs match');
  });

  test('displays verified badges', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    const verifiedBadges = await page.locator('.verified').count();
    expect(verifiedBadges).toBeGreaterThan(0);
  });

  test('shows correct masseur count', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.card', { timeout: 5000 });
    
    const headerText = await page.locator('.grid-header h2').textContent();
    expect(headerText).toContain('6 masseurs available');
  });
});
