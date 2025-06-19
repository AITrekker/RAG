/// <reference types="cypress" />
import './commands';

declare global {
  namespace Cypress {
    interface Chainable<Subject = any> {
      /**
       * Custom command to select DOM element by data-testid attribute.
       * @example cy.getByTestId('search-input')
       */
      getByTestId(value: string): Chainable<JQuery<HTMLElement>>;
    }
  }
}

// Add custom commands
Cypress.Commands.add('getByTestId', (testId: string) => {
  return cy.get(`[data-testid="${testId}"]`);
}); 