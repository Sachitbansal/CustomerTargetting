import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { HomePage } from './components/HomePage';
import { ModelStats } from './components/ModelStats';
import { Reports } from './components/Reports';

type Page = 'home' | 'reports' | 'modelStats';

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('home');
  const [isDark, setIsDark] = useState(false);

  const toggleTheme = () => {
    setIsDark(!isDark);
  };

  return (
    <div className={isDark ? 'dark' : ''}>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar 
          currentPage={currentPage} 
          setCurrentPage={setCurrentPage}
          isDark={isDark}
          toggleTheme={toggleTheme}
        />
        <main className="flex-1 transition-all duration-300">
          {currentPage === 'home' && <HomePage />}
          {currentPage === 'reports' && <Reports />}
          {currentPage === 'modelStats' && <ModelStats />}
        </main>
      </div>
    </div>
  );
}
