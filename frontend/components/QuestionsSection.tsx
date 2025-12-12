"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { ChevronDown, ChevronRight, Check, Lock, Plus, Send, Loader2 } from "lucide-react";

interface Question {
  text: string;
  answer: string;
  isChecked: boolean;
}

interface QuestionsSectionProps {
  title: string;
  type: "expert" | "client";
  questions: string[];
  answers: Record<string, string>;
  onAnswerChange: (questionIndex: number, answer: string) => void;
  onGenerateMore?: () => Promise<void>;
  isGeneratingMore?: boolean;
  isGeneratingQuestions?: boolean; // True when initial question generation is in progress
  onLockChange?: (locked: boolean) => void; // Callback when lock state changes
  onCheckedChange?: (checked: number[]) => void; // Callback when checked questions change
  initialLocked?: boolean; // Initial lock state from saved state
  initialChecked?: number[]; // Initial checked questions from saved state
  disabled?: boolean;
}

interface QuestionItemProps {
  question: string;
  answer: string;
  index: number;
  isChecked: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onToggleCheck: () => void;
  onAnswerChange: (answer: string) => void;
  disabled?: boolean;
}

function QuestionItem({
  question,
  answer,
  index,
  isChecked,
  isExpanded,
  onToggleExpand,
  onToggleCheck,
  onAnswerChange,
  disabled,
}: QuestionItemProps) {
  return (
    <div
      className={`border rounded-lg transition-all ${
        isChecked
          ? "border-green-500/30 bg-green-500/5 opacity-70"
          : "border-border bg-card"
      }`}
    >
      {/* Question header - always visible */}
      <div
        className="flex items-start gap-3 p-3 cursor-pointer"
        onClick={() => !isChecked && onToggleExpand()}
      >
        {/* Expand/collapse icon */}
        <button
          type="button"
          className="mt-0.5 text-muted-foreground hover:text-foreground transition-colors bg-transparent border-none p-0"
          onClick={(e) => {
            e.stopPropagation();
            if (!isChecked) onToggleExpand();
          }}
          disabled={isChecked}
        >
          {isExpanded && !isChecked ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {/* Question text */}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium leading-snug ${isChecked ? "line-through text-muted-foreground" : "text-foreground"}`}>
            <span className="text-muted-foreground mr-2">Q{index + 1}.</span>
            {isExpanded || question.length <= 120 
              ? question 
              : `${question.slice(0, 120)}…`}
          </p>
          {isChecked && answer && (
            <p className="text-xs text-muted-foreground mt-1 truncate">
              A: {answer.slice(0, 100)}{answer.length > 100 ? "…" : ""}
            </p>
          )}
        </div>

        {/* Check button */}
        <button
          type="button"
          className={`flex items-center justify-center w-6 h-6 rounded-md border transition-all ${
            isChecked
              ? "bg-green-500 border-green-500 text-white"
              : "border-border hover:border-green-500/50 hover:bg-green-500/10 text-muted-foreground"
          }`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleCheck();
          }}
          title={isChecked ? "Mark as unanswered" : "Mark as answered"}
          disabled={disabled}
        >
          <Check className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Answer textarea - expanded view */}
      {isExpanded && !isChecked && (
        <div className="px-3 pb-3 pt-0">
          <textarea
            className="w-full min-h-[80px] p-2 text-sm rounded-md border border-border bg-background text-foreground resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder="Enter your answer..."
            value={answer}
            onChange={(e) => onAnswerChange(e.target.value)}
            disabled={disabled}
          />
        </div>
      )}
    </div>
  );
}

export function QuestionsSection({
  title,
  type,
  questions,
  answers,
  onAnswerChange,
  onGenerateMore,
  isGeneratingMore,
  isGeneratingQuestions,
  onLockChange,
  onCheckedChange,
  initialLocked = false,
  initialChecked = [],
  disabled,
}: QuestionsSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false); // Collapsed by default
  const [isLockedIn, setIsLockedIn] = useState(initialLocked);
  const [expandedQuestions, setExpandedQuestions] = useState<Set<number>>(new Set()); // All collapsed by default
  const [checkedQuestions, setCheckedQuestions] = useState<Set<number>>(() => new Set(initialChecked));
  
  // Track if we've done initial setup (to avoid re-syncing after user interactions)
  const [hasInitialized, setHasInitialized] = useState(false);

  // Sync from props on initial load, then mark as initialized
  useEffect(() => {
    if (!hasInitialized) {
      // Apply any saved state from props
      if (initialLocked || initialChecked.length > 0) {
        setIsLockedIn(initialLocked);
        setCheckedQuestions(new Set(initialChecked));
      }
      // Always mark as initialized after first render
      setHasInitialized(true);
    }
  }, [initialLocked, initialChecked, hasInitialized]);

  // Sort questions: unchecked first, then checked
  const sortedQuestionIndices = useMemo(() => {
    const unchecked: number[] = [];
    const checked: number[] = [];
    questions.forEach((_, index) => {
      if (checkedQuestions.has(index)) {
        checked.push(index);
      } else {
        unchecked.push(index);
      }
    });
    return [...unchecked, ...checked];
  }, [questions, checkedQuestions]);

  const toggleQuestionExpand = useCallback((index: number) => {
    setExpandedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const toggleQuestionCheck = useCallback((index: number) => {
    setCheckedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
        // Collapse when checking
        setExpandedQuestions((exp) => {
          const newExp = new Set(exp);
          newExp.delete(index);
          return newExp;
        });
      }
      return next;
    });
  }, []);
  
  // Notify parent of checked changes OUTSIDE the state setter (after state updates)
  useEffect(() => {
    if (hasInitialized) {
      onCheckedChange?.(Array.from(checkedQuestions));
    }
  }, [checkedQuestions, hasInitialized, onCheckedChange]);

  const handleLockIn = useCallback(() => {
    // Remove unanswered questions from checked state
    // (In a real implementation, you might want to persist this)
    setIsLockedIn(true);
    setIsExpanded(false);
    onLockChange?.(true);
  }, [onLockChange]);

  const handleUnlock = useCallback(() => {
    setIsLockedIn(false);
    setIsExpanded(true);
    onLockChange?.(false);
  }, [onLockChange]);

  const unansweredCount = questions.filter((_, i) => !checkedQuestions.has(i)).length;
  const answeredCount = checkedQuestions.size;

  // Show generating indicator when no questions yet but generation is in progress
  if (questions.length === 0 && isGeneratingQuestions) {
    return (
      <div className="border border-border rounded-lg overflow-hidden">
        <div className="flex items-center gap-3 p-4 bg-muted/30">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <div>
            <h3 className="font-semibold text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground">Generating questions...</p>
          </div>
        </div>
      </div>
    );
  }
  
  if (questions.length === 0) {
    return null;
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Section header */}
      <div
        className={`flex items-center justify-between p-3 cursor-pointer transition-colors ${
          isLockedIn ? "bg-green-500/10" : "bg-muted/30 hover:bg-muted/50"
        }`}
        onClick={() => !isLockedIn && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          {isExpanded && !isLockedIn ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <h3 className="font-semibold text-foreground">{title}</h3>
          <span className="text-xs text-muted-foreground">
            ({answeredCount}/{questions.length} answered)
          </span>
          {isLockedIn && (
            <span className="flex items-center gap-1 text-xs text-green-500">
              <Lock className="h-3 w-3" />
              Locked
            </span>
          )}
        </div>
      </div>

      {/* Questions list */}
      {isExpanded && !isLockedIn && (
        <div className="p-3 space-y-2">
          {sortedQuestionIndices.map((originalIndex) => (
            <QuestionItem
              key={originalIndex}
              question={questions[originalIndex]}
              answer={answers[originalIndex.toString()] || ""}
              index={originalIndex}
              isChecked={checkedQuestions.has(originalIndex)}
              isExpanded={expandedQuestions.has(originalIndex)}
              onToggleExpand={() => toggleQuestionExpand(originalIndex)}
              onToggleCheck={() => toggleQuestionCheck(originalIndex)}
              onAnswerChange={(answer) => onAnswerChange(originalIndex, answer)}
              disabled={disabled || isLockedIn}
            />
          ))}

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 pt-3 border-t border-border mt-3">
            {onGenerateMore && (
              <button
                type="button"
                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                onClick={onGenerateMore}
                disabled={isGeneratingMore || disabled}
              >
                {isGeneratingMore ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
                Generate More
              </button>
            )}
            
            <button
              type="button"
              className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-green-500/50 text-green-500 hover:bg-green-500/10 transition-colors disabled:opacity-50"
              onClick={handleLockIn}
              disabled={disabled}
            >
              <Lock className="h-3.5 w-3.5" />
              Lock In ({answeredCount})
            </button>

            <button
              type="button"
              className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border bg-muted/30 text-muted-foreground cursor-not-allowed opacity-50"
              disabled
              title="Coming soon"
            >
              <Send className="h-3.5 w-3.5" />
              Send to {type === "expert" ? "Expert" : "Client"}
            </button>
          </div>
        </div>
      )}

      {/* Locked state - show unlock button */}
      {isLockedIn && (
        <div className="p-3 border-t border-border">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {answeredCount} questions answered and locked
            </span>
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={handleUnlock}
            >
              Unlock to edit
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default QuestionsSection;

