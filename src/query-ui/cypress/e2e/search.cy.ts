describe('Search functionality', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('performs a basic search', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('test query{enter}');

    cy.get('[data-testid="search-results"]')
      .should('be.visible');

    cy.get('[data-testid="result-count"]')
      .should('contain', 'results');
  });

  it('shows suggestions while typing', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('test');

    cy.get('[role="listbox"]')
      .should('be.visible')
      .find('[role="button"]')
      .should('have.length.at.least', 1);
  });

  it('navigates to search history', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('test query{enter}');

    cy.get('[data-testid="history-link"]').click();

    cy.url().should('include', '/history');

    cy.get('[data-testid="history-list"]')
      .should('be.visible')
      .find('[data-testid="history-item"]')
      .should('contain', 'test query');
  });

  it('shows validation error for short queries', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('a{enter}');

    cy.get('[role="alert"]')
      .should('contain', 'Search query must be at least 2 characters');
  });

  it('shows relevance indicators for results', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('test query{enter}');

    cy.get('[data-testid="search-results"]')
      .find('[data-testid="relevance-indicator"]')
      .should('be.visible');
  });

  it('allows copying source citations', () => {
    cy.get('input[placeholder="Search documents..."]')
      .type('test query{enter}');

    cy.get('[data-testid="search-results"]')
      .find('[data-testid="copy-citation"]')
      .first()
      .click();

    cy.window().then((win) => {
      cy.stub(win.navigator.clipboard, 'writeText').resolves();
    });
  });

  it('is responsive on mobile devices', () => {
    cy.viewport('iphone-x');

    cy.get('[data-testid="mobile-menu"]')
      .should('be.visible')
      .click();

    cy.get('[data-testid="nav-drawer"]')
      .should('be.visible');

    cy.get('input[placeholder="Search documents..."]')
      .type('test query{enter}');

    cy.get('[data-testid="search-results"]')
      .should('be.visible')
      .and('have.css', 'font-size', '14px');
  });
}); 