package com.bank.util;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.*;

/**
 * FinancialCalculator — pure Java implementations.
 * Compute-heavy functions suitable for GraalVM polyglot optimization.
 * Target: C via GraalVM Sulong (SLE'17 energy efficiency paper).
 */
public class FinancialCalculator {

    // ── Result types ──────────────────────────────────────────────────────────

    public record MonteCarloResult(
        double var95, double var99, double meanValue,
        double worstCase, double bestCase, int simulations) {}

    public record AmortizationRow(
        int month, double payment, double principal,
        double interest, double balance,
        double totalInterest, double totalPrincipal) {}

    public record FraudScore(
        double riskScore, int flagCount, List<String> flags) {}

    // ── 1. sortTransactionAmounts ─────────────────────────────────────────────
    // SLE'17: sorting → C saves ~52% energy over Java
    public static double[] sortTransactionAmounts(double[] amounts) {
        double[] copy = Arrays.copyOf(amounts, amounts.length);
        mergeSort(copy, 0, copy.length - 1);
        return copy;
    }

    private static void mergeSort(double[] arr, int l, int r) {
        if (l < r) {
            int m = l + (r - l) / 2;
            mergeSort(arr, l, m);
            mergeSort(arr, m + 1, r);
            merge(arr, l, m, r);
        }
    }

    private static void merge(double[] arr, int l, int m, int r) {
        double[] left  = Arrays.copyOfRange(arr, l, m + 1);
        double[] right = Arrays.copyOfRange(arr, m + 1, r + 1);
        int i = 0, j = 0, k = l;
        while (i < left.length && j < right.length)
            arr[k++] = left[i] <= right[j] ? left[i++] : right[j++];
        while (i < left.length)  arr[k++] = left[i++];
        while (j < right.length) arr[k++] = right[j++];
    }

    // ── 2. computeRiskScore ───────────────────────────────────────────────────
    // SLE'17: deep recursion → C++ saves ~40% energy over Java
    public static double computeRiskScore(double[] factors, double[] weights, int depth) {
        return recursiveScore(factors, weights, 0, factors.length, depth);
    }

    private static double recursiveScore(double[] f, double[] w, int start, int end, int depth) {
        if (depth == 0 || end - start <= 1) {
            double sum = 0;
            for (int i = start; i < end; i++) sum += f[i] * w[i];
            return sum;
        }
        int mid = start + (end - start) / 2;
        double left  = recursiveScore(f, w, start, mid, depth - 1);
        double right = recursiveScore(f, w, mid,   end, depth - 1);
        return (left + right) / 2.0;
    }

    // ── 3. runMonteCarloSimulation ────────────────────────────────────────────
    // SLE'17: tight numeric loop → C saves ~56% energy over Java
    public static MonteCarloResult runMonteCarloSimulation(
            double portfolioValue, double meanReturn, double volatility,
            int numSimulations, int horizonDays) {
        Random rng = new Random(42);
        double[] finalValues = new double[numSimulations];
        double dt     = 1.0 / 252.0;
        double sqrtDt = Math.sqrt(dt);

        for (int s = 0; s < numSimulations; s++) {
            double value = portfolioValue;
            for (int d = 0; d < horizonDays; d++) {
                double z = rng.nextGaussian();
                value *= Math.exp(
                    (meanReturn - 0.5 * volatility * volatility) * dt
                    + volatility * sqrtDt * z);
            }
            finalValues[s] = value;
        }

        Arrays.sort(finalValues);
        double sum = Arrays.stream(finalValues).sum();

        return new MonteCarloResult(
            portfolioValue - finalValues[(int)(numSimulations * 0.05)],
            portfolioValue - finalValues[(int)(numSimulations * 0.01)],
            sum / numSimulations,
            finalValues[0],
            finalValues[numSimulations - 1],
            numSimulations
        );
    }

    // ── 4. computeAmortizationSchedule ───────────────────────────────────────
    // SLE'17: iterative numeric loop → C saves ~52% energy over Java
    public static List<AmortizationRow> computeAmortizationSchedule(
            double principal, double annualRate, int termMonths) {
        List<AmortizationRow> schedule = new ArrayList<>(termMonths);
        double monthlyRate = annualRate / 12.0 / 100.0;
        double payment = principal * monthlyRate
            * Math.pow(1 + monthlyRate, termMonths)
            / (Math.pow(1 + monthlyRate, termMonths) - 1);

        double balance = principal;
        double totalInterest  = 0;
        double totalPrincipal = 0;

        for (int month = 1; month <= termMonths; month++) {
            double interest  = balance * monthlyRate;
            double princ     = Math.min(payment - interest, balance);
            balance         -= princ;
            totalInterest   += interest;
            totalPrincipal  += princ;

            schedule.add(new AmortizationRow(
                month, payment, princ, interest,
                Math.max(0, balance), totalInterest, totalPrincipal));
        }
        return schedule;
    }

    // ── 5. findFraudPatterns ──────────────────────────────────────────────────
    // SLE'17: combinatorial search → C saves ~58% energy over Java
    public static FraudScore findFraudPatterns(
            double[] amounts, long[] timestamps, String[] locations) {
        int n = amounts.length;
        int flags = 0;
        List<String> flagList = new ArrayList<>();

        // Velocity check: >5 transactions within 10 minutes
        for (int i = 0; i < n; i++) {
            int count = 0;
            for (int j = 0; j < n; j++)
                if (Math.abs(timestamps[i] - timestamps[j]) < 600_000L) count++;
            if (count > 5) { flags++; flagList.add("VELOCITY"); break; }
        }

        // Round number bias: >40% divisible by 50 or 100
        long roundCount = Arrays.stream(amounts)
            .filter(a -> a % 100 == 0 || a % 50 == 0).count();
        if (roundCount > n * 0.4) { flags++; flagList.add("ROUND_NUMBER_BIAS"); }

        // Rapid escalation: 3× consecutive increase
        for (int i = 1; i < n - 1; i++)
            if (amounts[i] > amounts[i-1] * 3 && amounts[i+1] > amounts[i] * 3) {
                flags++; flagList.add("RAPID_ESCALATION"); break;
            }

        // Geographic scatter: >2 unique locations within 1 hour
        Set<String> uniqueLocs = new HashSet<>();
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++)
                if (Math.abs(timestamps[i] - timestamps[j]) < 3_600_000L
                        && locations[i] != null
                        && !locations[i].equals(locations[j])) {
                    uniqueLocs.add(locations[i]);
                    uniqueLocs.add(locations[j]);
                }
        if (uniqueLocs.size() > 2) { flags++; flagList.add("GEO_SCATTER"); }

        return new FraudScore(Math.min(1.0, flags * 0.25), flags, flagList);
    }
}
